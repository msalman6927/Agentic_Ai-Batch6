from uuid import UUID

import pytest
from sqlalchemy import text

from medivault.dependencies import get_session_factory
from medivault.ingestion.extractor import PatientEntry
from medivault.services import patient_service, sales_service
from tests.integration.sse_helper import collect_sse, event_names, joined_tokens

CSV = b"""sale_date,item_name,quantity,unit_price
2026-01-05,Panadol,10,5.50
2026-01-06,Brufen,4,12.00
2026-01-10,Panadol,6,6.00
bad-date,X,1,1.00
"""


async def _reset_sales_tables() -> None:
    """Wipe sales so global summary assertions stay deterministic."""
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(text("DELETE FROM sales"))
        await session.execute(text("DELETE FROM sales_uploads"))
        await session.commit()


@pytest.mark.integration
async def test_sales_upload_and_summary(client) -> None:
    await _reset_sales_tables()
    resp = await client.post(
        "/sales/upload",
        files={"file": ("sales.csv", CSV, "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["row_count"] == 3
    assert body["error_count"] == 1

    resp = await client.get("/sales/summary")
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["item_count"] == 2
    panadol = next(i for i in summary["items"] if i["item_name"] == "Panadol")
    assert panadol["total_quantity"] == 16
    assert panadol["total_revenue"] == 91.00

    resp = await client.get("/sales", params={"item_name": "brufen"})
    assert resp.status_code == 200
    rows = resp.json()["items"]
    assert len(rows) == 1 and rows[0]["item_name"] == "Brufen"

    await sales_service.delete_upload(UUID(body["id"]))


@pytest.mark.integration
async def test_sales_summary_tool_via_agent(client) -> None:
    await _reset_sales_tables()
    patient = await patient_service.create_patient(
        PatientEntry(
            full_name="Ali Khan", aliases=[], conditions=["pain"], allergies=[]
        )
    )
    try:
        resp = await client.post(
            "/sales/upload",
            files={"file": ("sales.csv", CSV, "text/csv")},
        )
        assert resp.status_code == 201
        upload_id = UUID(resp.json()["id"])

        events = await collect_sse(
            client,
            {
                "message": "How well is Panadol selling? Give me the sales numbers.",
            },
        )
        names = event_names(events)
        assert "error" not in names, [e for e in events if e["event"] == "error"]
        assert "done" in names
        tool_names = [
            e["data"].get("tool") for e in events if e["event"] == "tool_call"
        ]
        assert "get_sales_summary" in tool_names, tool_names
        assert "panadol" in joined_tokens(events).lower()

        await sales_service.delete_upload(upload_id)
    finally:
        await patient_service.delete_patient(patient.id)
