from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from medivault.config import get_settings


@dataclass
class SparseHit:
    chunk_row_id: str
    chroma_id: str
    document_id: str | None
    chunk_index: int | None
    content: str
    rank_score: float
    doc_type: str | None = None


async def sparse_search(
    session: AsyncSession,
    query: str,
    *,
    doc_type: str | None = None,
    k: int | None = None,
) -> list[SparseHit]:
    limit = k or get_settings().retrieval_sparse_top_k
    rows = await session.execute(
        text(
            """
            SELECT dc.id, dc.chroma_id, dc.document_id::text, dc.chunk_index,
                   dc.content, ts_rank(dc.tsv, q) AS rank_score,
                   dc.meta->>'doc_type' AS doc_type
            FROM document_chunks dc,
                 plainto_tsquery('simple', :query) q
            WHERE dc.tsv @@ q
              AND (
                    CAST(:doc_type AS text) IS NULL
                    OR dc.meta->>'doc_type' = CAST(:doc_type AS text)
                  )
            ORDER BY rank_score DESC
            LIMIT :limit
            """
        ),
        {"query": query, "doc_type": doc_type, "limit": limit},
    )
    return [
        SparseHit(
            chunk_row_id=str(row[0]),
            chroma_id=str(row[1]),
            document_id=row[2],
            chunk_index=row[3],
            content=row[4],
            rank_score=float(row[5]),
            doc_type=row[6],
        )
        for row in rows
    ]
