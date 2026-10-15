from functools import lru_cache

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from medivault.config import get_settings


@lru_cache
def get_embedder() -> GoogleGenerativeAIEmbeddings:
    settings = get_settings()
    return GoogleGenerativeAIEmbeddings(
        model=settings.embedding_model,
        google_api_key=settings.require_gemini_api_key(),
    )


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    embedder = get_embedder()
    batch_size = settings.embedding_batch_size
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        vectors.extend(await embedder.aembed_documents(batch))
    return vectors


async def embed_query(text: str) -> list[float]:
    embedder = get_embedder()
    result = await embedder.aembed_query(text)
    return list(result)


def reset_embedder_cache() -> None:
    get_embedder.cache_clear()
