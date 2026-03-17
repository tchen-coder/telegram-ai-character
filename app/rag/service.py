import asyncio
import hashlib
import json
import logging
import threading
from datetime import UTC
from typing import Any, Protocol

import httpx

from app.config import get_settings
from app.models import RoleInfo

logger = logging.getLogger(__name__)


ROLE_KNOWLEDGE_SOURCE_FIELDS = (
    ("tags", "tags"),
    ("system_prompt", "system_prompt"),
    ("scenario", "scenario"),
    ("greeting_message", "greeting_message"),
)


def _chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    normalized = " ".join((text or "").split())
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _make_uuid(prefix: str, *parts: object) -> str:
    raw = "::".join([prefix, *[str(part) for part in parts]])
    return hashlib.md5(raw.encode("utf-8"), usedforsecurity=False).hexdigest()


def _graphql_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _graphql_value(value: Any) -> str:
    if isinstance(value, dict):
        items = []
        for key, val in value.items():
            if key == "operator" and isinstance(val, str):
                items.append(f"{key}: {val}")
            else:
                items.append(f"{key}: {_graphql_value(val)}")
        return "{ " + ", ".join(items) + " }"
    if isinstance(value, list):
        return "[" + ", ".join(_graphql_value(item) for item in value) + "]"
    if isinstance(value, str):
        return _graphql_string(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


class ChatMessageLike(Protocol):
    id: int
    user_id: str
    role_id: int
    message_type: str
    content: str
    created_at: Any


class WeaviateRAGService:
    def __init__(self) -> None:
        self._client: httpx.Client | None = None
        self._lock = threading.Lock()
        self._ready = False

    async def ensure_ready(self) -> None:
        await asyncio.to_thread(self._ensure_ready_sync)

    async def index_role_knowledge(self, role: RoleInfo) -> None:
        await asyncio.to_thread(self._index_role_knowledge_sync, role)

    async def index_chat_memory(self, message: ChatMessageLike) -> None:
        await asyncio.to_thread(self._index_chat_memory_sync, message)

    async def retrieve_context(
        self,
        *,
        role: RoleInfo,
        user_id: str,
        query: str,
    ):
        from app.rag.models import RAGContext, RetrievedDocument

        result = await asyncio.to_thread(
            self._retrieve_context_sync,
            role,
            user_id,
            query,
        )
        return RAGContext(
            role_knowledge=[
                RetrievedDocument(collection="RoleKnowledge", **item)
                for item in result["role_knowledge"]
            ],
            conversation_memory=[
                RetrievedDocument(collection="ConversationMemory", **item)
                for item in result["conversation_memory"]
            ],
        )

    async def clear_all(self) -> None:
        await asyncio.to_thread(self._clear_all_sync)

    async def rebuild_role_knowledge(self, roles: list[RoleInfo]) -> None:
        await asyncio.to_thread(self._rebuild_role_knowledge_sync, roles)

    async def list_role_knowledge(
        self,
        *,
        role_id: int,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_role_knowledge_sync, role_id, limit)

    async def list_conversation_memory(
        self,
        *,
        user_id: str,
        role_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_conversation_memory_sync, user_id, role_id, limit)

    def close(self) -> None:
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None
                self._ready = False

    def _base_url(self) -> str:
        settings = get_settings()
        return f"http://{settings.weaviate_host}:{settings.weaviate_http_port}"

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(base_url=self._base_url(), timeout=30.0)
        return self._client

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._http().request(method, path, **kwargs)
        response.raise_for_status()
        if response.content:
            return response.json()
        return None

    def _schema_class_payload(self, class_name: str) -> dict[str, Any]:
        if class_name == get_settings().weaviate_role_collection:
            properties = [
                {"name": "role_id", "dataType": ["int"]},
                {"name": "role_name", "dataType": ["text"]},
                {"name": "source_type", "dataType": ["text"]},
                {"name": "chunk_index", "dataType": ["int"]},
                {"name": "content", "dataType": ["text"]},
            ]
        else:
            properties = [
                {"name": "chat_history_id", "dataType": ["int"]},
                {"name": "user_id", "dataType": ["text"]},
                {"name": "role_id", "dataType": ["int"]},
                {"name": "message_type", "dataType": ["text"]},
                {"name": "content", "dataType": ["text"]},
                {"name": "created_at", "dataType": ["date"]},
            ]

        return {
            "class": class_name,
            "description": f"{class_name} for telegram-ai-character rag",
            "vectorizer": "text2vec-transformers",
            "properties": properties,
        }

    def _ensure_class(self, class_name: str) -> None:
        schema = self._request("GET", "/v1/schema")
        classes = {item["class"] for item in schema.get("classes", [])}
        if class_name in classes:
            return
        self._request("POST", "/v1/schema", json=self._schema_class_payload(class_name))

    def _delete_class(self, class_name: str) -> None:
        try:
            self._request("DELETE", f"/v1/schema/{class_name}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise

    def _ensure_ready_sync(self) -> None:
        with self._lock:
            if self._ready:
                return

            settings = get_settings()
            self._ensure_class(settings.weaviate_role_collection)
            self._ensure_class(settings.weaviate_memory_collection)
            self._ready = True
            logger.info("Weaviate classes ready")

    def _clear_all_sync(self) -> None:
        settings = get_settings()
        with self._lock:
            self._delete_class(settings.weaviate_memory_collection)
            self._delete_class(settings.weaviate_role_collection)
            self._ready = False
        self._ensure_ready_sync()
        logger.info("Weaviate collections cleared and recreated")

    def _rebuild_role_knowledge_sync(self, roles: list[RoleInfo]) -> None:
        settings = get_settings()
        with self._lock:
            self._delete_class(settings.weaviate_role_collection)
            self._ready = False
        self._ensure_ready_sync()
        for role in roles:
            self._index_role_knowledge_sync(role)
        logger.info("Weaviate role knowledge rebuilt: roles=%s", len(roles))

    def _upsert_object(self, *, class_name: str, uuid: str, properties: dict[str, Any]) -> None:
        payload = {"class": class_name, "id": uuid, "properties": properties}
        try:
            self._request("POST", "/v1/objects", json=payload)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 422 or "already exists" not in exc.response.text.lower():
                raise

    def _index_role_knowledge_sync(self, role: RoleInfo) -> None:
        self._ensure_ready_sync()
        settings = get_settings()

        role_chunks: list[tuple[str, dict[str, Any]]] = []
        for source_type, field_name in ROLE_KNOWLEDGE_SOURCE_FIELDS:
            raw = getattr(role, field_name, None)
            if isinstance(raw, list):
                raw = " ".join(raw)
            if not raw:
                continue
            for idx, chunk in enumerate(
                _chunk_text(
                    raw,
                    chunk_size=settings.weaviate_role_chunk_size,
                    overlap=settings.weaviate_role_chunk_overlap,
                )
            ):
                role_chunks.append(
                    (
                        _make_uuid("role", role.id, source_type, idx),
                        {
                            "role_id": role.id,
                            "role_name": role.role_name,
                            "source_type": source_type,
                            "chunk_index": idx,
                            "content": chunk,
                        },
                    )
                )

        for uuid, properties in role_chunks:
            self._upsert_object(
                class_name=settings.weaviate_role_collection,
                uuid=uuid,
                properties=properties,
            )

        logger.info(
            "Weaviate role knowledge indexed: role=%s chunks=%s",
            role.role_name,
            len(role_chunks),
        )

    def _index_chat_memory_sync(self, message: ChatMessageLike) -> None:
        if not getattr(message, "content", None):
            return
        message_type = getattr(message, "message_type", "")
        if hasattr(message_type, "value"):
            message_type = message_type.value
        if str(message_type) == "assistant_image":
            return
        self._ensure_ready_sync()
        settings = get_settings()
        self._upsert_object(
            class_name=settings.weaviate_memory_collection,
            uuid=_make_uuid("memory", message.id),
            properties={
                "chat_history_id": message.id,
                "user_id": message.user_id,
                "role_id": message.role_id,
                "message_type": message_type,
                "content": message.content,
                "created_at": message.created_at.replace(tzinfo=UTC).isoformat(),
            },
        )

    def _query_collection(
        self,
        *,
        class_name: str,
        query: str,
        where: dict[str, Any],
        limit: int,
        fields: list[str],
    ) -> list[dict[str, Any]]:
        alpha = get_settings().weaviate_hybrid_alpha
        field_expr = " ".join(fields + ["_additional { score }"])
        graphql = (
            "{ Get { "
            f"{class_name}("
            f"hybrid: {{ query: {_graphql_string(query)}, alpha: {alpha} }}, "
            f"where: {_graphql_value(where)}, "
            f"limit: {limit}"
            f") {{ {field_expr} }} "
            "} }"
        )

        payload = {"query": graphql}
        response = self._request("POST", "/v1/graphql", json=payload)
        if response.get("errors"):
            raise RuntimeError(f"Weaviate GraphQL error: {response['errors']}")
        return response.get("data", {}).get("Get", {}).get(class_name, [])

    def _list_collection(
        self,
        *,
        class_name: str,
        where: dict[str, Any],
        limit: int,
        fields: list[str],
        sort: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        field_expr = " ".join(fields + ["_additional { id }"])
        sort_expr = f", sort: {_graphql_value(sort)}" if sort else ""
        graphql = (
            "{ Get { "
            f"{class_name}("
            f"where: {_graphql_value(where)}, "
            f"limit: {limit}"
            f"{sort_expr}"
            f") {{ {field_expr} }} "
            "} }"
        )
        response = self._request("POST", "/v1/graphql", json={"query": graphql})
        if response.get("errors"):
            raise RuntimeError(f"Weaviate GraphQL error: {response['errors']}")
        return response.get("data", {}).get("Get", {}).get(class_name, [])

    def _retrieve_context_sync(self, role: RoleInfo, user_id: str, query: str) -> dict[str, Any]:
        self._ensure_ready_sync()
        settings = get_settings()

        role_where = {
            "path": ["role_id"],
            "operator": "Equal",
            "valueInt": role.id,
        }
        memory_where = {
            "operator": "And",
            "operands": [
                {"path": ["role_id"], "operator": "Equal", "valueInt": role.id},
                {"path": ["user_id"], "operator": "Equal", "valueText": user_id},
            ],
        }

        role_raw = self._query_collection(
            class_name=settings.weaviate_role_collection,
            query=query,
            where=role_where,
            limit=settings.weaviate_role_top_k,
            fields=["content", "role_id", "role_name", "source_type", "chunk_index"],
        )
        memory_raw = self._query_collection(
            class_name=settings.weaviate_memory_collection,
            query=query,
            where=memory_where,
            limit=settings.weaviate_memory_top_k,
            fields=["content", "chat_history_id", "user_id", "role_id", "message_type", "created_at"],
        )

        role_docs = self._serialize_objects(role_raw)
        memory_docs = self._serialize_objects(memory_raw)
        logger.info(
            "RAG retrieval: role=%s user=%s query=%r role_hits=%s memory_hits=%s",
            role.role_name,
            user_id,
            query,
            len(role_docs),
            len(memory_docs),
        )
        for index, item in enumerate(role_docs, start=1):
            logger.info(
                "RAG role hit %s: score=%s metadata=%s content=%r",
                index,
                item.get("score"),
                item.get("metadata"),
                item.get("content"),
            )
        for index, item in enumerate(memory_docs, start=1):
            logger.info(
                "RAG memory hit %s: score=%s metadata=%s content=%r",
                index,
                item.get("score"),
                item.get("metadata"),
                item.get("content"),
            )

        return {
            "role_knowledge": role_docs,
            "conversation_memory": memory_docs,
        }

    def _list_role_knowledge_sync(self, role_id: int, limit: int) -> list[dict[str, Any]]:
        self._ensure_ready_sync()
        settings = get_settings()
        objects = self._list_collection(
            class_name=settings.weaviate_role_collection,
            where={"path": ["role_id"], "operator": "Equal", "valueInt": role_id},
            limit=limit,
            fields=["content", "role_id", "role_name", "source_type", "chunk_index"],
            sort=[{"path": ["chunk_index"], "order": "asc"}],
        )
        return self._serialize_objects(objects)

    def _list_conversation_memory_sync(
        self,
        user_id: str,
        role_id: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        self._ensure_ready_sync()
        settings = get_settings()
        operands: list[dict[str, Any]] = [
            {"path": ["user_id"], "operator": "Equal", "valueText": user_id},
        ]
        if role_id is not None:
            operands.append({"path": ["role_id"], "operator": "Equal", "valueInt": role_id})

        where = operands[0] if len(operands) == 1 else {"operator": "And", "operands": operands}
        objects = self._list_collection(
            class_name=settings.weaviate_memory_collection,
            where=where,
            limit=limit,
            fields=["content", "chat_history_id", "user_id", "role_id", "message_type", "created_at"],
            sort=[{"path": ["created_at"], "order": "asc"}],
        )
        return self._serialize_objects(objects)

    @staticmethod
    def _serialize_objects(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for item in objects:
            metadata = {key: value for key, value in item.items() if key not in {"content", "_additional"}}
            additional = item.get("_additional", {})
            score = additional.get("score")
            serialized.append(
                {
                    "id": additional.get("id"),
                    "content": item.get("content", ""),
                    "score": score,
                    "metadata": metadata,
                }
            )
        return serialized


rag_service = WeaviateRAGService()
