"""Root FastAPI entrypoint for Vercel and local runs."""
import os
import sys
import traceback

root_dir = os.path.abspath(os.path.dirname(__file__))
src_dir = os.path.join(root_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from axiomcart.main import app
except Exception as exc:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI(title="AxiomCart Error Fallback")
    err_trace = traceback.format_exc()
    print(f"FATAL_STARTUP_ERROR: {err_trace}", file=sys.stderr)

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def fallback_handler(path: str):
        return JSONResponse(
            status_code=500,
            content={
                "status": "failed",
                "error": "Application startup error",
                "detail": str(exc),
                "traceback": err_trace,
            },
        )
