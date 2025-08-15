import contextlib
import os

from fastapi import FastAPI

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

# Mount each MCP server under a distinct path prefix, each exposing its streamable HTTP app
app.mount("/web_docs", web_docs_mcp.streamable_http_app())
app.mount("/date", date_mcp.streamable_http_app())


def main() -> None:
    port = int(os.environ.get("PORT", "8801"))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass


