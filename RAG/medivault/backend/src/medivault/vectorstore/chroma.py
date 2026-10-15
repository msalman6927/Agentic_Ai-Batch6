import contextlib
from collections.abc import Iterator

from chromadb import ClientAPI, HttpClient, PersistentClient
from chromadb.api.models.Collection import Collection

from medivault.config import get_settings
from medivault.vectorstore.collections import ALL_COLLECTIONS

_client: ClientAPI | None = None


def get_chroma() -> ClientAPI:
    global _client
    if _client is None:
        settings = get_settings()
        if settings.chroma_host:
            _client = HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        else:
            path = settings.chroma_path
            path.mkdir(parents=True, exist_ok=True)
            _client = PersistentClient(path=str(path))
    return _client


def get_collection(name: str) -> Collection:
    return get_chroma().get_or_create_collection(
        name=name, metadata={"hnsw:space": "cosine"}
    )


def iter_collections() -> Iterator[Collection]:
    for name in ALL_COLLECTIONS:
        yield get_collection(name)


def ensure_collections() -> None:
    collections = list(iter_collections())
    if not collections:  # pragma: no cover - defensive
        raise RuntimeError("no collections configured")


def reset_chroma_state() -> None:
    global _client
    if _client is not None:
        with contextlib.suppress(Exception):
            _client.reset()  # type: ignore[attr-defined]
    _client = None
