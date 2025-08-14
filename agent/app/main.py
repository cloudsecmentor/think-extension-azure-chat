from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .utils.llm import generate_reply
from .utils.mcp_session_manager import get_mcp_session_manager


logger = logging.getLogger("agent_service")
logging.basicConfig(level=logging.INFO)

# Load environment variables from a .env file when running locally
load_dotenv()

app = FastAPI(
    title="Agent Service",
    description="FastAPI application exposing a mocked agent endpoint.",
    version="0.1.0",
)


@app.on_event("startup")
async def startup_event():
    """Initialize MCP session manager on application startup."""
    logger.info("Application startup: Initializing MCP connections.")
    mcp_manager = get_mcp_session_manager()
    await mcp_manager.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    """Close MCP connections on application shutdown."""
    logger.info("Application shutdown: Closing MCP connections.")
    mcp_manager = get_mcp_session_manager()
    await mcp_manager.close()

class AgentRequest(BaseModel):
    user_query: str
    history: Optional[List[Any]] = Field(default_factory=list)


@app.post("/agent")
async def agent(request: AgentRequest):
    logger.info(f"Received agent request: {request}")
    reply = await generate_reply(user_query=request.user_query, history=request.history)
    # reply = await generate_mock_reply(user_query=request.user_query, history=request.history)

    return JSONResponse(content={"message": reply}, status_code=200)


