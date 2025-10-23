from typing import Optional

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from dotenv import load_dotenv, find_dotenv
from app.utils import start_aci_job

load_dotenv(find_dotenv())

app = FastAPI()


class MessageRequest(BaseModel):
    threadId: Optional[str] = Field(None, min_length=1)
    userId: Optional[str] = Field(None, min_length=1)
    content: str = Field(..., min_length=1)
    context: Optional[str] = Field(None, min_length=1)



@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/think")
async def create_message(
    req: MessageRequest,
    user_id: Optional[str] = Header(None, alias="user-id"),
    chat_thread_id: Optional[str] = Header(None, alias="chat-thread-id"),
):
    try:
        # Prefer headers; fallback to body for backward compatibility
        resolved_thread_id = chat_thread_id or req.threadId
        resolved_user_id = user_id or req.userId

        if not resolved_thread_id or not resolved_user_id:
            raise HTTPException(status_code=400, detail="Missing required user-id or chat-thread-id")

        extra_env = {
            "THREAD_ID": resolved_thread_id,
            "USER_ID": resolved_user_id,
            "CONTENT": req.content,
        }
        if req.context:
            extra_env["CONTEXT"] = req.context

        result = start_aci_job(extra_env=extra_env)
        return {
            "status": "started",
            "job": result.get("job"),
            "resourceGroup": result.get("resourceGroup"),
            "environment": result.get("environment"),
            "threadId": resolved_thread_id,
            "userId": resolved_user_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
