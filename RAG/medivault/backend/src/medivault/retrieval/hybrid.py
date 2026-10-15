from dataclasses import dataclass, field

from medivault.config import get_settings
from medivault.dependencies import get_session_factory
from medivault.llm.embeddings import embed_query
from medivault.retrieval.dense import dense_search
from medivault.retrieval.fusion import rrf_fuse
from medivault.retrieval.sparse import sparse_search


@dataclass
class RetrievalHit:
    chroma_id: str
    content: str
    score: float
    doc_type: str | None = None
    document_id: str | None = None
    chunk_index: int | None = None
    dense_rank: int | None = None
    sparse_rank: int | None = None
    dense_score: float | None = None
    snippet: str = ""
    extras: dict = field(default_factory=dict)

    def to_payload(self) -> dict:
        return {
            "rank": None,
            "ref_type": f"{self.doc_type}_chunk" if self.doc_type else "chunk",
            "ref_id": self.chroma_id,
            "title": self.extras.get("title"),
            "snippet": self.snippet,
            "score": round(self.score, 4),
        }


def _snippet(content: str, length: int = 220) -> str:
    compact = " ".join(content.split())
    return compact[:length]


async def hybrid_search(
    query: str,
    *,
    doc_type: str | None = None,
    k: int | None = None,
) -> list[RetrievalHit]:
    """Dense (Chroma) + sparse (Postgres FTS) fused with RRF; hydrated from Postgres."""
    settings = get_settings()
    top_k = k or settings.retrieval_top_k

    query_vector = await embed_query(query)
    dense_hits = dense_search(query_vector, doc_type=doc_type)

    factory = get_session_factory()
    async with factory() as session:
        sparse_hits = await sparse_search(session, query, doc_type=doc_type)

        dense_ids = [hit.chroma_id for hit in dense_hits]
        sparse_ids = [hit.chroma_id for hit in sparse_hits]
        fused = rrf_fuse([dense_ids, sparse_ids], k=settings.rrf_k)

        dense_rank = {cid: i + 1 for i, cid in enumerate(dense_ids)}
        sparse_rank = {cid: i + 1 for i, cid in enumerate(sparse_ids)}
        dense_by_id = {hit.chroma_id: hit for hit in dense_hits}
        sparse_by_id = {hit.chroma_id: hit for hit in sparse_hits}

        hits: list[RetrievalHit] = []
        for chroma_id, rrf_score in fused[:top_k]:
            dense = dense_by_id.get(chroma_id)
            sparse = sparse_by_id.get(chroma_id)
            content = sparse.content if sparse else (dense.content if dense else "")
            hits.append(
                RetrievalHit(
                    chroma_id=chroma_id,
                    content=content,
                    score=rrf_score,
                    doc_type=(
                        dense.doc_type
                        if dense and dense.doc_type
                        else (sparse.doc_type if sparse else None)
                    ),
                    document_id=(
                        dense.document_id
                        if dense and dense.document_id
                        else (sparse.document_id if sparse else None)
                    ),
                    chunk_index=(
                        dense.chunk_index
                        if dense and dense.chunk_index is not None
                        else (sparse.chunk_index if sparse else None)
                    ),
                    dense_rank=dense_rank.get(chroma_id),
                    sparse_rank=sparse_rank.get(chroma_id),
                    dense_score=dense.score if dense else None,
                    snippet=_snippet(content),
                )
            )
        return hits
