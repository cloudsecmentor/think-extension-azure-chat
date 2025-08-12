from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, List, Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse
import httpx

from app.schemas import ThinkRequest, AsyncThinkRequest
from app.store import JobStatus, JobStore


logger = logging.getLogger("fastapi_async_chatbot")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Asynchronous Chatbot Interface",
    description=(
        "FastAPI application demonstrating asynchronous, polling-based chatbot "
        "workflow with a mocked LLM."
    ),
    version="0.1.0",
)

AGENT_URL = os.getenv("AGENT_URL", "http://agent:5500")


async def call_agent_service(user_query: str, history: Optional[List[Any]]) -> str:
    url = f"{AGENT_URL}/agent"
    payload: dict[str, Any] = {"user_query": user_query, "history": history}
    logger.info("Calling agent at %s", url)
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.RequestError as exc:
        logger.exception("Failed to reach agent service: %s", exc)
        raise HTTPException(status_code=502, detail="Agent service unavailable") from exc
    except httpx.HTTPStatusError as exc:
        logger.exception("Agent service returned error: %s", exc)
        raise HTTPException(status_code=502, detail="Agent service error") from exc

    data = response.json()
    reply = data.get("message")
    if not isinstance(reply, str):
        logger.error("Invalid response from agent: %s", data)
        raise HTTPException(status_code=502, detail="Invalid response from agent")
    return reply


@app.on_event("startup")
async def on_startup() -> None:
    app.state.job_store = JobStore()
    logger.info("JobStore initialized")


@app.post("/think")
async def think(request: ThinkRequest):
    logger.info("Received request: %s", request)
    reply = await call_agent_service(user_query=request.user_query, history=request.history)
    return JSONResponse(content={"message": reply}, status_code=200)

@app.post("/asyncthink")
async def asyncthink(request: AsyncThinkRequest):
    logger.info("Received request: %s", request)
    store: JobStore = app.state.job_store

    # Polling mode: id present, no new query
    if request.id is not None and request.user_query is None:
        job = await store.get_job(request.id)
        if job is None:
            raise HTTPException(status_code=404, detail="Invalid or expired ID")
        if job.status == JobStatus.pending:
            return {"reply": "not ready"}
        # Completed
        reply = job.result or ""
        await store.delete_job(job.id)
        return {"reply": reply}

    # Submission mode: new query present
    if request.user_query is not None:
        job_id = uuid4()
        await store.create_job(job_id, request.history, request.user_query)

        # Schedule background processing without blocking the response
        asyncio.create_task(process_job(job_id, request.history, request.user_query, store))
        return JSONResponse(content={"id": str(job_id)}, status_code=202)

    # Invalid payload
    raise HTTPException(
        status_code=400,
        detail=(
            "Invalid request. Provide either 'user_query' to submit a new query or 'id' to poll."
        ),
    )

@app.post("/think/v2")
async def think_v2(payload: Any = Body(...)):
    """
    Accepts arbitrary JSON payload and returns a 200 OK with a static message.
    """
    logger.info("Received request: %s", payload)
    return JSONResponse(content={"message": "Hello World"}, status_code=200)


async def process_job(
    job_id: UUID, history: Optional[List[Any]], user_query: str, store: JobStore
) -> None:
    logger.info("Started processing request %s", job_id)
    reply = await call_agent_service(user_query=user_query, history=history)
    await store.set_result(job_id, reply)
    logger.info("Completed processing request %s", job_id)
