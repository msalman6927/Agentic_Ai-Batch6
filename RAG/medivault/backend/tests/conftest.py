from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from medivault.dependencies import dispose_engine_if_created
from medivault.main import app


@pytest.fixture(autouse=True)
async def _dispose_engine_between_tests() -> AsyncIterator[None]:
    """Fresh event loop per test — pooled connections must die with it."""
    yield
    await dispose_engine_if_created()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
