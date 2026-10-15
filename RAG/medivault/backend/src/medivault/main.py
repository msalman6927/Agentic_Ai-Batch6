from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from medivault import __version__
from medivault.config import get_settings
from medivault.routers import (
    chat,
    consultations,
    conversations,
    documents,
    health,
    medicines,
    patients,
    sales,
)
from medivault.utils.errors import MediVaultError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    from medivault.vectorstore.chroma import ensure_collections

    ensure_collections()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="MediVault",
        version=__version__,
        description="Agentic clinical RAG for doctors",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(medicines.router)
    app.include_router(patients.router)
    app.include_router(chat.router)
    app.include_router(conversations.router)
    app.include_router(consultations.router)
    app.include_router(sales.router)

    @app.exception_handler(MediVaultError)
    async def medivault_error_handler(
        request: Request, exc: MediVaultError
    ) -> JSONResponse:
        payload: dict[str, Any] = {"error": {"code": exc.code, "detail": exc.detail}}
        return JSONResponse(status_code=exc.status_code, content=payload)

    return app


app = create_app()
