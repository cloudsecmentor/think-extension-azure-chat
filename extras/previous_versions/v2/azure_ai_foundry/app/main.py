from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
import os


app = FastAPI()


def _get_project_client() -> AIProjectClient:
    conn_str = os.getenv(
        "AZURE_AI_FOUNDRY_CONN_STR"
    )
    return AIProjectClient.from_connection_string(
        credential=DefaultAzureCredential(),
        conn_str=conn_str,
    )


project_client = _get_project_client()


class MessageRequest(BaseModel):
    content: str


@app.post("/message")
async def post_message(body: MessageRequest):
    thread = None
    assistant_id = os.getenv("AZURE_AI_FOUNDRY_ASSISTANT_ID")
    try:
        agent = project_client.agents.get_agent(assistant_id)

        thread = project_client.agents.create_thread()

        project_client.agents.create_message(
            thread_id=thread.id,
            role="user",
            content=body.content,
        )

        project_client.agents.create_and_process_run(
            thread_id=thread.id,
            agent_id=agent.id,
        )

        messages = project_client.agents.list_messages(thread_id=thread.id)

        first_message = None
        for text_message in messages.text_messages:
            first_message = text_message
            break

        if first_message is None:
            raise HTTPException(status_code=204, detail="No messages returned")

        return {"message": first_message.as_dict()}
    finally:
        if thread is not None:
            try:
                project_client.agents.delete_thread(thread_id=thread.id)
            except Exception:
                pass


@app.get("/health")
async def health():
    return {"status": "ok"}


