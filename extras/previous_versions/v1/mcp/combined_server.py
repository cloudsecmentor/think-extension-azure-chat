import contextlib
import os
import logging

from fastapi import FastAPI
from starlette.responses import JSONResponse

# Import the FastMCP instances from each server module
from web_docs.main import mcp as web_docs_mcp
from date.main import mcp as date_mcp


# Create a combined lifespan to manage both session managers
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(web_docs_mcp.session_manager.run())
        await stack.enter_async_context(date_mcp.session_manager.run())
        yield


app = FastAPI(lifespan=lifespan)
logger = logging.getLogger(__name__)

# Mount each MCP server under a distinct path prefix, each exposing its streamable HTTP app
app.mount("/web_docs", web_docs_mcp.streamable_http_app())
app.mount("/date", date_mcp.streamable_http_app())

# Lightweight health checks under each prefix to support sidecar readiness probes and client preflight checks
@app.get("/web_docs/health")
async def web_docs_health():
    return JSONResponse({"status": "ok", "server": "web_docs"})


@app.get("/date/health")
async def date_health():
    return JSONResponse({"status": "ok", "server": "date"})


@app.get("/health")
async def root_health():
    return JSONResponse({"status": "ok", "server": "combined"})


@app.get("/health/web_docs")
async def health_web_docs_alias():
    return JSONResponse({"status": "ok", "server": "web_docs"})


@app.get("/health/date")
async def health_date_alias():
    return JSONResponse({"status": "ok", "server": "date"})


def main() -> None:
    # Use a dedicated MCP_PORT to avoid platform-provided PORT (e.g., App Service sets PORT=80)
    port = int(os.environ.get("MCP_PORT") or "8801")
    import uvicorn
    logger.info(f"Starting MCP combined server on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass


