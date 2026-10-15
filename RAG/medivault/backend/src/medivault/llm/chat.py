from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from medivault.config import get_settings


@lru_cache
def get_chat_model(*, temperature: float | None = None) -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.gemini_chat_model,
        google_api_key=settings.require_gemini_api_key(),
        temperature=(settings.chat_temperature if temperature is None else temperature),
        max_output_tokens=settings.chat_max_output_tokens,
    )


def reset_chat_model_cache() -> None:
    get_chat_model.cache_clear()
