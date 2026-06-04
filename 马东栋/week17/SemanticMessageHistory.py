from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import redis
import ulid
from pymilvus import DataType, MilvusClient


class ChatRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    LLM = "llm"
    TOOL = "tool"
    ASSISTANT = "assistant"

    @classmethod
    def coerce(cls, value: "str | ChatRole") -> "ChatRole":
        if isinstance(value, cls):
            return value
        v = str(value).lower()
        for m in cls:
            if m.value == v:
                return m
        raise ValueError(f"unknown role: {value!r}")


@dataclass
class ChatMessage:
    role: ChatRole
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: int = 0
    message_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "content": self.content,
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp,
            "message_id": self.message_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ChatMessage":
        return cls(
            role=ChatRole.coerce(d["role"]),
            content=d["content"],
            metadata=d.get("metadata", {}) or {},
            timestamp=int(d.get("timestamp", 0)),
            message_id=d.get("message_id"),
        )

def safe_collection(name: str) -> str:
    return "".join(c if c.isalnum() or c == "_" else "_" for c in name)


def session_key(session_id: str) -> str:
    return f"mrvl:session:{session_id}:messages"

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


class SemanticMessageHistory:
    """Per-session message store with semantic recall (Redis + Milvus)."""

    def __init__(
        self,
        name: str,
        session_id: str,
        redis_url: str,
        milvus_host: str,
        milvus_port: int,
        vectorizer: FakeVectorizer,
        *,
        distance_threshold: float = 0.7,
        ttl: int | None = None,
    ) -> None:
        self.name = name
        self.session_id = session_id
        self.distance_threshold = distance_threshold
        self.vectorizer = vectorizer
        self._r = redis.Redis.from_url(redis_url, decode_responses=True)
        self._collection = safe_collection(name)
        self._m = MilvusClient(uri=f"http://{milvus_host}:{milvus_port}")
        self.ttl = ttl

        if not self._m.has_collection(self._collection):
            self._create_collection()

    def _create_collection(self) -> None:
        schema = self._m.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=self.vectorizer.dim)
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=8192)
        schema.add_field(field_name="payload", datatype=DataType.JSON)
        schema.add_field(field_name="ts", datatype=DataType.INT64)
        schema.add_field(field_name="session_id", datatype=DataType.VARCHAR, max_length=128)
        idx = self._m.prepare_index_params()
        idx.add_index(field_name="vector", metric_type="L2", index_type="IVF_FLAT", params={"nlist": 1024})
        self._m.create_collection(collection_name=self._collection, schema=schema, index_params=idx)

    def add_message(self, role: "str | ChatRole", content: str, metadata: dict[str, Any] | None = None) -> ChatMessage:
        msg = ChatMessage(
            role=ChatRole.coerce(role),
            content=content,
            metadata=metadata or {},
            timestamp=int(time.time() * 1000),
            message_id=str(ulid.new()),
        )
        self._r.rpush(session_key(self.session_id), json.dumps(msg.to_dict(), ensure_ascii=False))
        if self.ttl is not None:
            self._r.expire(session_key(self.session_id), self.ttl)

        self._m.upsert(
            collection_name=self._collection,
            data=[{
                "id": msg.message_id,
                "vector": self.vectorizer.to_list(content),
                "text": content,
                "payload": {"role": msg.role.value, "metadata": msg.metadata, "timestamp": msg.timestamp},
                "ts": msg.timestamp,
                "session_id": self.session_id,
            }],
        )
        return msg

    def add(self, messages: list[dict[str, Any] | ChatMessage]) -> None:
        for m in messages:
            if isinstance(m, ChatMessage):
                self.add_message(m.role, m.content, m.metadata)
            else:
                self.add_message(m["role"], m["content"], m.get("metadata", {}))

    def get_recent(self, limit: int = 10) -> list[ChatMessage]:
        raw = self._r.lrange(session_key(self.session_id), -limit, -1)
        return [ChatMessage.from_dict(json.loads(r)) for r in raw]

    def search(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
        """Top-K messages from THIS session, ranked by similarity to ``query``."""
        vec = self.vectorizer.to_list(query)
        raw = self._m.search(
            collection_name=self._collection,
            data=[vec],
            limit=top_k,
            filter=f'session_id == "{self.session_id}"',
            output_fields=["text", "payload", "ts", "session_id"],
        )
        results: list[dict[str, Any]] = []
        for h in raw[0] if raw else []:
            dist = h.get("distance", float("inf"))
            if dist > self.distance_threshold:
                continue
            entity = h.get("entity", {}) or {}
            payload = entity.get("payload", {}) or {}
            try:
                role = ChatRole.coerce(payload.get("role", "user"))
            except ValueError:
                role = ChatRole.USER
            msg = ChatMessage(
                role=role,
                content=entity.get("text", ""),
                metadata=payload.get("metadata", {}),
                timestamp=int(payload.get("timestamp", 0)),
                message_id=h.get("id"),
            )
            results.append({"message": msg, "distance": dist})
        return results

    def clear(self) -> None:
        self._r.delete(session_key(self.session_id))
        if self._m.has_collection(self._collection):
            self._m.delete(collection_name=self._collection, filter=f'session_id == "{self.session_id}"')

    def __len__(self) -> int:
        return int(self._r.llen(session_key(self.session_id)))

    def __repr__(self) -> str:
        return f"SemanticMessageHistory(name={self.name!r}, session={self.session_id!r})"

def main() -> None:
    hist = SemanticMessageHistory(
        name="demo-history",
        session_id="user-42",
        redis_url="redis://localhost:6379/0",
        milvus_host="localhost",
        milvus_port=19530,
        vectorizer=FakeVectorizer(dim=32),
        distance_threshold=2.0,  # permissive for the fake vectorizer
        ttl=120,
    )

    print("=== SemanticMessageHistory demo ===")
    hist.add([
        {"role": "user", "content": "hello, how are you?"},
        {"role": "llm", "content": "I'm doing fine, thanks."},
        {"role": "user", "content": "what is the weather going to be today?"},
        {"role": "llm", "content": "I don't know"},
    ])

    print("\nRecent 10 messages:")
    for m in hist.get_recent(10):
        print(f"  {m.role.value}: {m.content!r}")

    print("\nSemantic search for 'howdy':")
    for r in hist.search("howdy"):
        print(f"  (d={r['distance']:.4f}) {r['message'].role.value}: {r['message'].content!r}")

    hist.clear()


if __name__ == "__main__":
    main()
