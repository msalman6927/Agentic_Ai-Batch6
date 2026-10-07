import hashlib
from pathlib import Path
from uuid import UUID

import psycopg
from pgvector.psycopg import register_vector

from institution_rag.config import require_database_url


def connect() -> psycopg.Connection:
    conn = psycopg.connect(require_database_url())
    register_vector(conn)
    return conn


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def already_ingested(conn: psycopg.Connection, content_hash: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM documents WHERE content_hash = %s",
        (content_hash,),
    ).fetchone()
    return row is not None


def save_chunks(
    conn: psycopg.Connection,
    *,
    filename: str,
    content_hash: str,
    file_size_bytes: int,
    chunks: list[str],
    vectors: list[list[float]],
    embedding_model: str,
    embedding_dims: int,
) -> UUID:
    if len(chunks) != len(vectors):
        raise ValueError(
            f"chunks ({len(chunks)}) and vectors ({len(vectors)}) mismatch"
        )
    with conn.transaction():
        document_id = conn.execute(
            """
            INSERT INTO documents
                (filename, content_hash, file_size_bytes, chunk_count,
                 embedding_model, embedding_dims)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                filename,
                content_hash,
                file_size_bytes,
                len(chunks),
                embedding_model,
                embedding_dims,
            ),
        ).fetchone()[0]

        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO chunks
                    (document_id, chunk_index, content, embedding)
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (document_id, index, content, vector)
                    for index, (content, vector) in enumerate(
                        zip(chunks, vectors, strict=True)
                    )
                ],
            )
    return document_id
