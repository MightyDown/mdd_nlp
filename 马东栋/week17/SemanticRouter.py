from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import redis
import ulid
from pymilvus import DataType, MilvusClient

@dataclass
class Route:
    name: str
    references: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    distance_threshold: float | None = None  # per-route override; falls back to router default


@dataclass
class RouteMatch:
    name: str
    distance: float
    metadata: dict[str, Any] = field(default_factory=dict)

def safe_collection(name: str) -> str:
    return "".join(c if c.isalnum() or c == "_" else "_" for c in name)


def router_key(name: str) -> str:
    return f"mrvl:{name}:routes"


def stats_key(name: str) -> str:
    return f"mrvl:{name}:stats"

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

    def embed_many(self, texts: list[str]) -> list[np.ndarray]:
        return [self.embed(t) for t in texts]

    def to_list(self, text: str) -> list[float]:
        return self.embed(text).tolist()

class SemanticRouter:
    """Map a query to its closest route. None if all candidates exceed threshold."""

    def __init__(
        self,
        name: str,
        routes: list[Route],
        redis_url: str,
        milvus_host: str,
        milvus_port: int,
        vectorizer: FakeVectorizer,
        *,
        distance_threshold: float = 0.3,
    ) -> None:
        if not routes:
            raise ValueError("at least one route is required")
        self.name = name
        self.routes = routes
        self.distance_threshold = distance_threshold
        self.vectorizer = vectorizer
        self._r = redis.Redis.from_url(redis_url, decode_responses=True)
        self._collection = safe_collection(name)
        self._m = MilvusClient(uri=f"http://{milvus_host}:{milvus_port}")

        # (Re)build the collection from scratch each time we initialize
        if self._m.has_collection(self._collection):
            self._m.drop_collection(self._collection)
        self._create_collection()

        # Persist route metadata to Redis
        self._r.delete(router_key(self.name))
        for r in routes:
            self._r.hset(
                router_key(self.name),
                r.name,
                f"{r.distance_threshold if r.distance_threshold is not None else distance_threshold}|"
                + json.dumps(r.metadata, ensure_ascii=False),
            )

        # Embed all references and upsert
        all_refs = [ref for r in routes for ref in r.references]
        if not all_refs:
            raise ValueError("at least one route must have references")
        vecs = [v.tolist() for v in vectorizer.embed_many(all_refs)]
        ids = [str(ulid.new()) for _ in all_refs]
        ts = int(time.time() * 1000)
        rows: list[dict[str, Any]] = []
        i = 0
        for r in routes:
            for ref in r.references:
                rows.append({
                    "id": ids[i],
                    "vector": vecs[i],
                    "text": ref,
                    "payload": {
                        "route_name": r.name,
                        "ref_text": ref,
                        "metadata": r.metadata,
                        "ts": ts,
                    },
                    "ts": ts,
                })
                i += 1
        self._m.upsert(collection_name=self._collection, data=rows)

    def _create_collection(self) -> None:
        schema = self._m.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=self.vectorizer.dim)
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=4096)
        schema.add_field(field_name="payload", datatype=DataType.JSON)
        schema.add_field(field_name="ts", datatype=DataType.INT64)
        idx = self._m.prepare_index_params()
        idx.add_index(field_name="vector", metric_type="L2", index_type="IVF_FLAT", params={"nlist": 1024})
        self._m.create_collection(collection_name=self._collection, schema=schema, index_params=idx)

    def __call__(self, query: str, *, top_k: int = 1) -> RouteMatch | None:
        vec = self.vectorizer.to_list(query)
        raw = self._m.search(
            collection_name=self._collection,
            data=[vec],
            limit=top_k * 5,
            output_fields=["text", "payload"],
            search_params={"metric_type": "L2", "params": {"nprobe": 16}},
        )
        hits = raw[0] if raw else []
        if not hits:
            self._r.hincrby(stats_key(self.name), "misses", 1)
            return None

        best_per_route: dict[str, float] = {}
        for h in hits:
            payload = h.get("entity", {}).get("payload", {}) or {}
            rn = payload.get("route_name", "")
            dist = h.get("distance", float("inf"))
            if not rn:
                continue
            if rn not in best_per_route or dist < best_per_route[rn]:
                best_per_route[rn] = dist

        if not best_per_route:
            self._r.hincrby(stats_key(self.name), "misses", 1)
            return None

        best_name = min(best_per_route, key=best_per_route.get)  # type: ignore[arg-type]
        best_dist = best_per_route[best_name]
        route_obj = next((r for r in self.routes if r.name == best_name), None)
        threshold = (
            route_obj.distance_threshold
            if route_obj is not None and route_obj.distance_threshold is not None
            else self.distance_threshold
        )
        if best_dist > threshold:
            self._r.hincrby(stats_key(self.name), "misses", 1)
            return None

        self._r.hincrby(stats_key(self.name), "hits", 1)
        return RouteMatch(
            name=best_name,
            distance=best_dist,
            metadata=route_obj.metadata if route_obj else {},
        )

    def route(self, query: str) -> RouteMatch | None:
        return self(query)

    def clear(self) -> None:
        self._r.delete(router_key(self.name))
        self._r.delete(stats_key(self.name))
        if self._m.has_collection(self._collection):
            self._m.drop_collection(self._collection)

    def __repr__(self) -> str:
        return f"SemanticRouter(name={self.name!r}, routes={[r.name for r in self.routes]})"


def main() -> None:
    router = SemanticRouter(
        name="demo-router",
        routes=[
            Route(name="greeting", references=["hello", "hi", "good morning"], distance_threshold=2.0),
            Route(name="farewell", references=["bye", "goodbye", "see you"], distance_threshold=2.0),
        ],
        redis_url="redis://localhost:6379/0",
        milvus_host="localhost",
        milvus_port=19530,
        vectorizer=FakeVectorizer(dim=32),
        distance_threshold=2.0,
    )

    print("=== SemanticRouter demo ===")
    for q in ["Hi, good morning", "Bye, see you later", "What is the time?"]:
        m = router(q)
        if m:
            print(f"  {q!r:35s} → {m.name} (d={m.distance:.4f})")
        else:
            print(f"  {q!r:35s} → (no route)")

    router.clear()


if __name__ == "__main__":
    main()
