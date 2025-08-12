from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.schemas import AgentRequest
from app.utils.mock_llm import generate_mock_reply


logger = logging.getLogger("agent_service")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Agent Service",
    description="FastAPI application exposing a mocked agent endpoint.",
    version="0.1.0",
)


@app.post("/agent")
async def agent(request: AgentRequest):
    logger.info("Received agent request: %s", request)
    reply = await generate_mock_reply(user_query=request.user_query, history=request.history)
    return JSONResponse(content={"message": reply}, status_code=200)


