from httpx import AsyncClient


async def test_health_returns_envelope(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "database" in body
    assert "chroma" in body


async def test_unknown_route_uses_fastapi_404(client: AsyncClient) -> None:
    response = await client.get("/definitely-not-a-route")
    assert response.status_code == 404
