from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import redis
import ulid
from pymilvus import DataType, MilvusClient


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def exact_key(name: str, text: str) -> str:
    return f"mrvl:{name}:exact:{hash_text(text)}"


def stats_key(name: str) -> str:
    return f"mrvl:{name}:stats"


def safe_collection(name: str) -> str:
    """Milvus only allows [a-zA-Z0-9_] in collection names."""
    return "".join(c if c.isalnum() or c == "_" else "_" for c in name)

@dataclass
class CacheEntry:
    prompt: str
    response: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheHit:
    response: str
    prompt: str
    distance: float
    cache_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

class FakeVectorizer:
    """Deterministic hash-based vectorizer. Same text → same vector."""

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    def embed(self, text: str) -> np.ndarray:
        seed = int.from_bytes(text.encode("utf-8")[:8].ljust(8, b"\x00"), "big") or 1
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(self.dim).astype("float32")
        v /= np.linalg.norm(v)
        return v

    def to_list(self, text: str) -> list[float]:
        return self.embed(text).tolist()

class SemanticCache:
    """Two-tier LLM response cache: Redis exact + Milvus ANN."""

    def __init__(
        self,
        name: str,
        redis_url: str,
        milvus_host: str,
        milvus_port: int,
        vectorizer: FakeVectorizer,
        *,
        ttl: int = 3600,
        distance_threshold: float = 0.1,
    ) -> None:
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        self.name = name
        self.ttl = ttl
        self.distance_threshold = distance_threshold
        self.vectorizer = vectorizer
        self._r = redis.Redis.from_url(redis_url, decode_responses=True)
        self._collection = safe_collection(name)
        self._m = MilvusClient(uri=f"http://{milvus_host}:{milvus_port}")

        # Create the collection on first use
        if not self._m.has_collection(self._collection):
            self._create_collection()

    def _create_collection(self) -> None:
        schema = self._m.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=self.vectorizer.dim)
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=8192)
        schema.add_field(field_name="payload", datatype=DataType.JSON)
        schema.add_field(field_name="ts", datatype=DataType.INT64)
        idx = self._m.prepare_index_params()
        idx.add_index(field_name="vector", metric_type="L2", index_type="IVF_FLAT", params={"nlist": 1024})
        self._m.create_collection(collection_name=self._collection, schema=schema, index_params=idx)

    def store(self, prompt: str, response: str, metadata: dict[str, Any] | None = None) -> str:
        """Persist a prompt/response pair. Returns the cache id."""
        metadata = metadata or {}
        cache_id = str(ulid.new())
        vec = self.vectorizer.to_list(prompt)

        # 1) Milvus
        self._m.upsert(
            collection_name=self._collection,
            data=[{
                "id": cache_id,
                "vector": vec,
                "text": prompt,
                "payload": {"response": response, "metadata": metadata},
                "ts": int(time.time() * 1000),
            }],
        )

        # 2) Redis exact-key
        self._r.set(
            exact_key(self.name, prompt),
            json.dumps({"response": response, "metadata": metadata, "cache_id": cache_id}, ensure_ascii=False),
            ex=self.ttl,
        )
        self._r.hincrby(stats_key(self.name), "writes", 1)
        return cache_id

    def check(self, prompt: str, *, top_k: int = 1) -> list[CacheHit]:
        """Look up by exact key first, then by ANN if no exact hit."""
        # 1) Redis exact path
        raw = self._r.get(exact_key(self.name, prompt))
        if raw:
            data = json.loads(raw)
            self._r.hincrby(stats_key(self.name), "exact_hits", 1)
            return [CacheHit(
                response=data["response"],
                prompt=prompt,
                distance=0.0,
                cache_id=data.get("cache_id", ""),
                metadata=data.get("metadata", {}),
            )]

        # 2) Milvus semantic path
        vec = self.vectorizer.to_list(prompt)
        raw_hits = self._m.search(
            collection_name=self._collection,
            data=[vec],
            limit=top_k,
            output_fields=["text", "payload"],
            search_params={"metric_type": "L2", "params": {"nprobe": 16}},
        )

        hits: list[CacheHit] = []
        for h in raw_hits[0] if raw_hits else []:
            dist = h.get("distance", float("inf"))
            if dist > self.distance_threshold:
                continue
            entity = h.get("entity", {}) or {}
            payload = entity.get("payload", {}) or {}
            hits.append(CacheHit(
                response=payload.get("response", ""),
                prompt=entity.get("text", ""),
                distance=dist,
                cache_id=h.get("id", ""),
                metadata=payload.get("metadata", {}),
            ))

        if hits:
            self._r.hincrby(stats_key(self.name), "semantic_hits", 1)
        else:
            self._r.hincrby(stats_key(self.name), "misses", 1)
        return hits

    def clear(self) -> None:
        for k in self._r.scan_iter(f"mrvl:{self.name}:*", count=200):
            self._r.delete(k)
        if self._m.has_collection(self._collection):
            self._m.drop_collection(self._collection)
        self._create_collection()

    def stats(self) -> dict[str, int]:
        raw = self._r.hgetall(stats_key(self.name)) or {}
        return {k: int(v) for k, v in raw.items()}

    def __len__(self) -> int:
        if not self._m.has_collection(self._collection):
            return 0
        return self._m.get_collection_stats(self._collection).get("row_count", 0)

    def __repr__(self) -> str:
        return f"SemanticCache(name={self.name!r}, ttl={self.ttl}, threshold={self.distance_threshold})"


def main() -> None:
    cache = SemanticCache(
        name="demo-semantic",
        redis_url="redis://localhost:6379/0",
        milvus_host="localhost",
        milvus_port=19530,
        vectorizer=FakeVectorizer(dim=32),
        ttl=120,
        distance_threshold=2.0,  # permissive to make the demo work with a fake vectorizer
    )

    print("=== SemanticCache demo ===")
    pairs = [
        ("What is the capital of France?", "Paris"),
        ("Tell me a joke", "Why did the chicken cross the road?"),
    ]
    for p, r in pairs:
        cache.store(p, r)

    queries = [
        "What is the capital of France?",  # exact
        "What is the capital city of France?",  # near (with fake vec, distance is high)
        "Tell me a joke",  # exact
    ]
    for q in queries:
        hits = cache.check(q)
        if hits:
            h = hits[0]
            print(f"  [HIT  d={h.distance:.4f}] {q!r} → {h.response!r}")
        else:
            print(f"  [MISS         ] {q!r}")

    print("\nstats:", cache.stats())
    print("size :", len(cache))
    cache.clear()


if __name__ == "__main__":
    main()
