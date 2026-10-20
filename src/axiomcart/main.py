"""AxiomCart FastAPI service entrypoint."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from axiomcart.api.routes import router
from axiomcart.config import settings
from axiomcart.observability.logging import get_logger, setup_logging

logger = get_logger("axiomcart.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown hooks."""
    setup_logging(settings.log_level)
    logger.info("axiomcart_service_starting", env=settings.app_env)
    yield
    logger.info("axiomcart_service_shutting_down")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title="AxiomCart Voice AI",
        description="Voice-first customer service coordinator with LiveKit, LangGraph, and Salesforce.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    # Mount public static files if present (for local runs)
    import os
    from fastapi.staticfiles import StaticFiles
    public_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "public"))
    if os.path.isdir(public_dir):
        app.mount("/", StaticFiles(directory=public_dir, html=True), name="static")

    return app



app = create_app()


def main():
    """CLI entrypoint for running the web application."""
    uvicorn.run("axiomcart.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
