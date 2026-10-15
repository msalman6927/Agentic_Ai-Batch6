from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from medivault.dependencies import get_session
from medivault.schemas.common import HealthResponse

router = APIRouter(tags=["health"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _check_database(session: AsyncSession) -> str:
    try:
        await session.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"error: {type(exc).__name__}: {exc}"


def _check_chroma() -> str:
    try:
        from medivault.vectorstore.chroma import get_chroma

        get_chroma().heartbeat()
        return "ok"
    except ImportError:
        return "not_configured"
    except Exception as exc:  # noqa: BLE001
        return f"error: {type(exc).__name__}: {exc}"


@router.get("/health", response_model=HealthResponse)
async def health(session: SessionDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        database=await _check_database(session),
        chroma=_check_chroma(),
    )
