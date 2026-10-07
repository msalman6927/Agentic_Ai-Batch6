import time
from pathlib import Path

from institution_rag import store
from institution_rag.chunker import chunk_text
from institution_rag.config import EMBEDDING_DIMS, EMBEDDING_MODEL
from institution_rag.embedder import embed_texts
from institution_rag.loader import load_pdf


def ingest(path: Path, *, reingest: bool = False) -> None:
    started = time.perf_counter()
    content_hash = store.file_sha256(path)

    with store.connect() as conn:
        if not reingest and store.already_ingested(conn, content_hash):
            print(
                f"SKIP    {path.name} - already ingested (sha256 {content_hash[:12]})"
            )
            return

        text = load_pdf(path)
        chunks = chunk_text(text)
        print(f"LOAD    {path.name} - {len(text)} chars extracted")
        print(f"CHUNK   {len(chunks)} chunks (size 1000 / overlap 200)")

        vectors = embed_texts(chunks)
        print(
            f"EMBED   {len(vectors)} vectors x {EMBEDDING_DIMS} dims ({EMBEDDING_MODEL})"
        )

        if reingest:
            conn.execute(
                "DELETE FROM documents WHERE content_hash = %s", (content_hash,)
            )

        document_id = store.save_chunks(
            conn,
            filename=path.name,
            content_hash=content_hash,
            file_size_bytes=path.stat().st_size,
            chunks=chunks,
            vectors=vectors,
            embedding_model=EMBEDDING_MODEL,
            embedding_dims=EMBEDDING_DIMS,
        )
        conn.commit()

    elapsed = time.perf_counter() - started
    print(
        f"SAVED   document {document_id} - {len(chunks)} rows in `chunks` ({elapsed:.2f}s)"
    )
