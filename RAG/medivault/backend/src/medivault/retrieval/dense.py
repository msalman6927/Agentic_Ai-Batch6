from collections.abc import Sequence
from dataclasses import dataclass

from medivault.config import get_settings
from medivault.vectorstore.chroma import get_collection
from medivault.vectorstore.collections import (
    MEDICINE_CHUNKS,
    META_CHUNK_INDEX,
    META_DOC_TYPE,
    META_DOCUMENT_ID,
    PATIENT_CHUNKS,
)

_COLLECTION_BY_DOC_TYPE = {
    "medicine": MEDICINE_CHUNKS,
    "patient": PATIENT_CHUNKS,
}


@dataclass
class DenseHit:
    chroma_id: str
    document_id: str | None
    doc_type: str | None
    chunk_index: int | None
    content: str
    distance: float
    score: float


def _collection_names(doc_type: str | None) -> list[str]:
    if doc_type in _COLLECTION_BY_DOC_TYPE:
        return [_COLLECTION_BY_DOC_TYPE[doc_type]]
    return [MEDICINE_CHUNKS, PATIENT_CHUNKS]


def dense_search(
    query_vector: Sequence[float],
    *,
    doc_type: str | None = None,
    k: int | None = None,
) -> list[DenseHit]:
    settings = get_settings()
    per_collection = k or settings.retrieval_dense_top_k
    hits: list[DenseHit] = []
    embeddings: list[Sequence[float]] = [query_vector]
    for name in _collection_names(doc_type):
        collection = get_collection(name)
        if collection.count() == 0:
            continue
        result = collection.query(
            query_embeddings=embeddings,
            n_results=per_collection,
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids") or [[]]
        docs = result.get("documents") or [[]]
        metas = result.get("metadatas") or [[]]
        dists = result.get("distances") or [[]]
        for chroma_id, content, meta, distance in zip(
            ids[0], docs[0], metas[0], dists[0], strict=True
        ):
            raw_meta = meta or {}
            doc_id = raw_meta.get(META_DOCUMENT_ID)
            kind = raw_meta.get(META_DOC_TYPE)
            chunk_index = raw_meta.get(META_CHUNK_INDEX)
            hits.append(
                DenseHit(
                    chroma_id=chroma_id,
                    document_id=str(doc_id) if isinstance(doc_id, str) else None,
                    doc_type=str(kind) if isinstance(kind, str) else None,
                    chunk_index=(chunk_index if isinstance(chunk_index, int) else None),
                    content=content or "",
                    distance=float(distance),
                    score=round(1.0 - float(distance), 4),
                )
            )
    hits.sort(key=lambda hit: hit.distance)
    return hits[: per_collection * len(_collection_names(doc_type))]
