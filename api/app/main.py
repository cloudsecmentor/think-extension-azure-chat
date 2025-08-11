from __future__ import annotations

import asyncio
import logging
from typing import Any, List, Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse

from app.schemas import ThinkRequest
from app.store import JobStatus, JobStore
from app.utils.mock_llm import generate_mock_reply


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


@app.on_event("startup")
async def on_startup() -> None:
    app.state.job_store = JobStore()
    logger.info("JobStore initialized")


@app.post("/think")
async def think(request: ThinkRequest):
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
    reply = await generate_mock_reply(user_query=user_query, history=history)
    await store.set_result(job_id, reply)
    logger.info("Completed processing request %s", job_id)
