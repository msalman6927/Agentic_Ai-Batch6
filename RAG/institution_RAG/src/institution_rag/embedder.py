import math

from google import genai
from google.genai import types

from institution_rag.config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIMS,
    EMBEDDING_MODEL,
    require_gemini_api_key,
)


def _client() -> genai.Client:
    return genai.Client(api_key=require_gemini_api_key())


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _embed_batch(
    client: genai.Client, texts: list[str], task_type: str
) -> list[list[float]]:
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=EMBEDDING_DIMS,
        ),
    )
    vectors = [[float(value) for value in item.values] for item in result.embeddings]
    if len(vectors) != len(texts):
        raise RuntimeError(f"Expected {len(texts)} embeddings, got {len(vectors)}")
    return [_normalize(vector) for vector in vectors]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = _client()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + EMBEDDING_BATCH_SIZE]
        vectors.extend(_embed_batch(client, batch, "RETRIEVAL_DOCUMENT"))
    return vectors


def embed_query(text: str) -> list[float]:
    client = _client()
    return _embed_batch(client, [text], "RETRIEVAL_QUERY")[0]


def smoke_test() -> int:
    vectors = embed_texts(["institution rag ingestion smoke test"])
    return len(vectors[0])
