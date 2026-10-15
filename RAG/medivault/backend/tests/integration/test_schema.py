import pytest
from sqlalchemy import text

from medivault.dependencies import get_session_factory


@pytest.mark.integration
async def test_all_tables_exist() -> None:
    expected = {
        "alembic_version",
        "consultations",
        "conversations",
        "document_chunks",
        "documents",
        "medicine_interactions",
        "medicines",
        "message_citations",
        "message_tool_calls",
        "messages",
        "patients",
        "sales",
        "sales_uploads",
    }
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        actual = {row[0] for row in rows}
    assert expected <= actual, expected - actual


@pytest.mark.integration
async def test_document_chunks_tsv_is_generated() -> None:
    factory = get_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT column_name, is_generated "
                    "FROM information_schema.columns "
                    "WHERE table_name = 'document_chunks' AND column_name = 'tsv'"
                )
            )
        ).one()
        assert row[1] == "ALWAYS"
