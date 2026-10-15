import pytest

from medivault.vectorstore.chroma import get_chroma, get_collection
from medivault.vectorstore.collections import ALL_COLLECTIONS


@pytest.mark.integration
async def test_heartbeat() -> None:
    assert get_chroma().heartbeat() > 0


@pytest.mark.integration
async def test_collections_exist() -> None:
    for name in ALL_COLLECTIONS:
        collection = get_collection(name)
        assert collection.name == name
