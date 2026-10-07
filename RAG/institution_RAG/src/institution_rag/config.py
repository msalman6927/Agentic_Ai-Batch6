import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.environ.get("database_url", "").strip().strip("'\"")
GEMINI_API_KEY = os.environ.get("gemini_api_key", "").strip().strip("'\"")

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMS = 768
EMBEDDING_BATCH_SIZE = 100
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

CHAT_MODEL = "gemini-flash-latest"
CHAT_MODEL_FALLBACK = "gemini-3.8-flash"
CHAT_TEMPERATURE = 0.4
CHAT_MAX_OUTPUT_TOKENS = 1024
TOP_K = 5
RELEVANCE_DISTANCE = 0.5
HISTORY_LIMIT = 20
MAX_MESSAGE_CHARS = 4000


def require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError(
            f"database_url is missing. Set it in {PROJECT_ROOT / '.env'}"
        )
    return DATABASE_URL


def require_gemini_api_key() -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            f"gemini_api_key is missing. Set it in {PROJECT_ROOT / '.env'}"
        )
    return GEMINI_API_KEY
