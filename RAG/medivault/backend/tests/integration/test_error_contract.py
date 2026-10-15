import pytest

MISSING_UUID = "00000000-0000-0000-0000-000000000000"


def _assert_envelope(response, expected_code: str, expected_status: int) -> None:
    assert response.status_code == expected_status, response.text
    body = response.json()
    assert "error" in body, body
    assert body["error"]["code"] == expected_code
    assert body["error"]["detail"]


@pytest.mark.integration
async def test_not_found_envelopes(client) -> None:
    resp = await client.get(f"/patients/{MISSING_UUID}")
    _assert_envelope(resp, "not_found", 404)

    resp = await client.get(f"/consultations/{MISSING_UUID}")
    _assert_envelope(resp, "not_found", 404)

    resp = await client.get(f"/documents/{MISSING_UUID}")
    _assert_envelope(resp, "not_found", 404)

    resp = await client.post("/consultations/confirm", json={"draft_id": MISSING_UUID})
    _assert_envelope(resp, "not_found", 404)

    resp = await client.delete(f"/sales/uploads/{MISSING_UUID}")
    _assert_envelope(resp, "not_found", 404)


@pytest.mark.integration
async def test_validation_envelopes(client) -> None:
    resp = await client.post(
        "/sales/upload", files={"file": ("note.txt", b"hello", "text/plain")}
    )
    _assert_envelope(resp, "ingest_failed", 422)

    bad_csv = b"item_name,quantity\nPanadol,5\n"
    resp = await client.post(
        "/sales/upload", files={"file": ("sales.csv", bad_csv, "text/csv")}
    )
    _assert_envelope(resp, "validation_error", 422)


@pytest.mark.integration
async def test_unknown_route_uses_fastapi_shape_not_envelope(client) -> None:
    resp = await client.get("/no-such-route")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}
