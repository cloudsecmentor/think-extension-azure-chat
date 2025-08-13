from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from app.schemas import AgentRequest
from app.utils.llm import generate_reply


logger = logging.getLogger("agent_service")
logging.basicConfig(level=logging.INFO)

# Load environment variables from a .env file when running locally
load_dotenv()

app = FastAPI(
    title="Agent Service",
    description="FastAPI application exposing a mocked agent endpoint.",
    version="0.1.0",
)


@app.post("/agent")
async def agent(request: AgentRequest):
    logger.info(f"Received agent request: {request}")
    reply = await generate_reply(user_query=request.user_query, history=request.history)
    # reply = await generate_mock_reply(user_query=request.user_query, history=request.history)

    return JSONResponse(content={"message": reply}, status_code=200)


