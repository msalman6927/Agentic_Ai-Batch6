from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pizza_world.api.v1 import admin, auth, chat, kitchen
from pizza_world.config import settings
from pizza_world.db.models import Base
from pizza_world.db.session import dispose_engine, get_engine
from pizza_world.services.checkpointer import aclose_checkpointer, get_checkpointer
from pizza_world.services.runtime import get_graph


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await get_checkpointer()  # create checkpoint tables on Neon
    await get_graph()
    try:
        yield
    finally:
        await aclose_checkpointer()
        await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(title="Pizza World Agent", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(admin.router)
    app.include_router(kitchen.router)

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "pizza-world-agent"}

    return app


app = create_app()


def main() -> None:
    """Dev entrypoint. On Windows psycopg needs a SelectorEventLoop, so run uvicorn
    inside one instead of `uvicorn run` (which would use ProactorEventLoop).
    """
    import uvicorn

    from pizza_world.core.runner import run

    config = uvicorn.Config("pizza_world.main:app", host="127.0.0.1", port=8000, reload=False)
    server = uvicorn.Server(config)
    run(server.serve())


if __name__ == "__main__":
    main()
