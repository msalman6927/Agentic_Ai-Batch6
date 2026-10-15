from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID, uuid4

from chromadb.api.types import Where

from medivault.config import get_settings
from medivault.llm.embeddings import embed_query, embed_texts
from medivault.vectorstore.chroma import get_collection
from medivault.vectorstore.collections import (
    CONSULTATION_MEMORY,
    META_CONVERSATION_ID,
    META_ROLE,
)


async def remember_turn(*, conversation_id: UUID, role: str, content: str) -> None:
    """Persist a chat turn into the memory collection for later hybrid recall."""
    if not content.strip():
        return
    vectors = await embed_texts([content])
    if not vectors:
        return
    embeddings: list[Sequence[float]] = [vectors[0]]
    collection = get_collection(CONSULTATION_MEMORY)
    collection.upsert(
        ids=[str(uuid4())],
        documents=[content],
        metadatas={
            META_CONVERSATION_ID: str(conversation_id),
            META_ROLE: role,
        },
        embeddings=embeddings,
    )


async def search_memory(
    query: str, *, conversation_id: UUID | None = None, k: int | None = None
) -> list[dict[str, Any]]:
    settings = get_settings()
    top_k = k or settings.history_retrieval_top_k
    collection = get_collection(CONSULTATION_MEMORY)
    if collection.count() == 0:
        return []
    vector = await embed_query(query)
    embeddings: list[Sequence[float]] = [vector]
    where: Where | None = (
        cast(Where, {META_CONVERSATION_ID: str(conversation_id)})
        if conversation_id is not None
        else None
    )
    result = collection.query(
        query_embeddings=embeddings,
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    hits: list[dict[str, Any]] = []
    ids = result.get("ids") or [[]]
    docs = result.get("documents") or [[]]
    metas = result.get("metadatas") or [[]]
    dists = result.get("distances") or [[]]
    for chunk_id, content, meta, distance in zip(
        ids[0], docs[0], metas[0], dists[0], strict=True
    ):
        hits.append(
            {
                "id": chunk_id,
                "content": content or "",
                "role": (meta or {}).get(META_ROLE),
                "conversation_id": (meta or {}).get(META_CONVERSATION_ID),
                "score": round(1.0 - float(distance), 4),
            }
        )
    return hits


async def recent_turns(
    conversation_id: UUID, *, limit: int | None = None
) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from medivault.db.models import Message
    from medivault.dependencies import get_session_factory

    window = limit or get_settings().history_recent_window
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(window)
        )
        turns = [
            {"role": row.role, "content": row.content} for row in reversed(list(rows))
        ]
        return turns
