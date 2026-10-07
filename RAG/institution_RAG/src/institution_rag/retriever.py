from dataclasses import dataclass

from pgvector import Vector

from institution_rag.config import TOP_K
from institution_rag.embedder import embed_query
from institution_rag.store import connect

SNIPPET_CHARS = 120


@dataclass
class Source:
    chunk_index: int
    score: float
    distance: float
    filename: str
    snippet: str
    content: str


def retrieve(query: str, k: int = TOP_K) -> tuple[list[Source], float]:
    query_vector = Vector(embed_query(query))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.chunk_index,
                   c.embedding <=> %s AS distance,
                   d.filename,
                   c.content
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            ORDER BY c.embedding <=> %s
            LIMIT %s
            """,
            (query_vector, query_vector, k),
        ).fetchall()

    sources = [
        Source(
            chunk_index=row[0],
            score=round(1.0 - float(row[1]), 3),
            distance=round(float(row[1]), 3),
            filename=row[2],
            snippet=row[3][:SNIPPET_CHARS],
            content=row[3],
        )
        for row in rows
    ]
    best_distance = sources[0].distance if sources else 2.0
    return sources, best_distance
