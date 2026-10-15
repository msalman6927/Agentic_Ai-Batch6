from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic_settings import BaseSettings, SettingsConfigDict

from medivault.utils.errors import ConfigError

MEDIVAULT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = MEDIVAULT_ROOT / ".env"


_LIBPQ_ONLY_PARAMS = ("sslmode", "channel_binding", "gssencmode")


def _strip_sslmode(url: str) -> tuple[str, str | None]:
    """asyncpg rejects libpq-only params (`sslmode`, `channel_binding`, …).

    Pull them out of the DSN; return the sslmode value for connect_args handling.
    """
    parsed = urlparse(url)
    if not parsed.query:
        return url, None
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    sslmode = params.pop("sslmode", None)
    for key in _LIBPQ_ONLY_PARAMS:
        params.pop(key, None)
    cleaned = urlunparse(parsed._replace(query=urlencode(params)))
    return cleaned, sslmode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "medivault"
    environment: str = "development"

    database_url: str = ""
    gemini_api_key: str = ""

    gemini_chat_model: str = "gemini-flash-latest"
    gemini_chat_model_fallback: str = "gemini-3.8-flash"
    embedding_model: str = "gemini-embedding-001"
    embedding_dims: int = 768
    embedding_batch_size: int = 100

    chroma_persist_dir: str = ".chroma"
    chroma_host: str = ""
    chroma_port: int = 8000
    uploads_dir: str = ".uploads"
    max_pdf_bytes: int = 25 * 1024 * 1024
    max_sales_csv_bytes: int = 5 * 1024 * 1024

    chat_temperature: float = 0.2
    chat_max_output_tokens: int = 2048
    max_message_chars: int = 4000

    retrieval_top_k: int = 6
    retrieval_dense_top_k: int = 8
    retrieval_sparse_top_k: int = 8
    rrf_k: int = 60
    min_confidence: float = 0.45

    max_agent_steps: int = 8
    history_recent_window: int = 6
    history_retrieval_top_k: int = 4

    chunk_size: int = 1200
    chunk_overlap: int = 200

    @property
    def chroma_path(self) -> Path:
        path = Path(self.chroma_persist_dir)
        return path if path.is_absolute() else MEDIVAULT_ROOT / path

    @property
    def uploads_path(self) -> Path:
        path = Path(self.uploads_dir)
        return path if path.is_absolute() else MEDIVAULT_ROOT / path

    def require_database_url(self) -> str:
        raw = self._normalized_database_url()
        if not raw:
            raise ConfigError(f"database_url is missing. Set it in {ENV_FILE}")
        return _strip_sslmode(raw)[0]

    def database_ssl_mode(self) -> str | None:
        raw = self._normalized_database_url()
        if not raw:
            raise ConfigError(f"database_url is missing. Set it in {ENV_FILE}")
        return _strip_sslmode(raw)[1]

    def _normalized_database_url(self) -> str:
        raw = self.database_url.strip().strip("'\"")
        if raw.startswith("postgres://"):
            raw = "postgresql://" + raw.removeprefix("postgres://")
        if raw.startswith("postgresql://"):
            raw = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
        return raw

    def require_gemini_api_key(self) -> str:
        key = self.gemini_api_key.strip().strip("'\"")
        if not key:
            raise ConfigError(f"gemini_api_key is missing. Set it in {ENV_FILE}")
        return key


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
