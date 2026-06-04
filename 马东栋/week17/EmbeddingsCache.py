from __future__ import annotations

import hashlib
import pickle
import time
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import redis

def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def key(name: str, text: str) -> str:
    return f"mrvl:{name}:exact:{hash_text(text)}"


def stats_key(name: str) -> str:
    return f"mrvl:{name}:stats"


@dataclass
class CacheEntry:
    text: str
    embedding: list[float]

class EmbeddingsCache:
    """Redis-only exact-key cache for embeddings.

    Args:
        name:       cache name (used as key namespace).
        redis_url:  e.g. ``redis://localhost:6379/0``.
        ttl:        seconds before each entry expires.
    """

    def __init__(self, name: str, redis_url: str, ttl: int = 3600) -> None:
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        self.name = name
        self.ttl = ttl
        self._r = redis.Redis.from_url(redis_url, decode_responses=True)

    def lookup(self, text: str) -> list[float] | None:
        raw = self._r.get(key(self.name, text))
        if raw is None:
            self._r.hincrby(stats_key(self.name), "misses", 1)
            return None
        self._r.hincrby(stats_key(self.name), "hits", 1)
        return pickle.loads(raw.encode("latin-1") if isinstance(raw, str) else raw)

    def store(self, text: str, embedding: list[float]) -> None:
        self._r.set(
            key(self.name, text),
            pickle.dumps(embedding).decode("latin-1"),
            ex=self.ttl,
        )
        self._r.hincrby(stats_key(self.name), "writes", 1)

    def store_many(self, texts: Iterable[str], embeddings: list[list[float]]) -> None:
        texts = list(texts)
        if len(texts) != len(embeddings):
            raise ValueError(f"length mismatch: {len(texts)} vs {len(embeddings)}")
        pipe = self._r.pipeline(transaction=False)
        for t, e in zip(texts, embeddings, strict=True):
            pipe.set(key(self.name, t), pickle.dumps(e).decode("latin-1"), ex=self.ttl)
        pipe.execute()
        self._r.hincrby(stats_key(self.name), "writes", len(texts))

    def clear(self) -> None:
        for k in self._r.scan_iter(f"mrvl:{self.name}:*", count=200):
            self._r.delete(k)

    def stats(self) -> dict[str, int]:
        raw = self._r.hgetall(stats_key(self.name)) or {}
        return {k: int(v) for k, v in raw.items()}

    def __repr__(self) -> str:
        return f"EmbeddingsCache(name={self.name!r}, ttl={self.ttl})"

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

    def embed_many(self, texts: Iterable[str]) -> list[np.ndarray]:
        return [self.embed(t) for t in texts]

def main() -> None:
    cache = EmbeddingsCache(name="demo-emb", redis_url="redis://localhost:6379/0", ttl=60)
    vec = FakeVectorizer(dim=16)

    print("=== EmbeddingsCache demo ===")
    texts = ["hello", "good morning", "how are you?", "hello", "good morning"]
    for t in texts:
        t0 = time.time()
        cached = cache.lookup(t)
        if cached is not None:
            print(f"  [HIT   {(time.time()-t0)*1000:6.2f}ms] {t!r}")
        else:
            v = vec.embed(t)
            cache.store(t, v.tolist())
            print(f"  [MISS  {(time.time()-t0)*1000:6.2f}ms] {t!r} → embedded ({len(v)}d)")

    print("\nstats:", cache.stats())
    cache.clear()
    print("cleared.")


if __name__ == "__main__":
    main()
