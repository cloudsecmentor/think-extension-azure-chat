# think-extension-azure-chat
Thinking extension service for Azure Chat, https://github.com/microsoft/azurechat

## FastAPI Asynchronous Chatbot Interface

This repository includes a FastAPI app that implements an asynchronous, polling-based chatbot interface with a mocked LLM, per the PRD. It accepts a new query, returns a request `id` immediately (202 Accepted), processes in the background, and supports polling the same endpoint to retrieve the final result.

### Run locally

1. Install dependencies (Python 3.10+):

```bash
pip install fastapi "uvicorn[standard]" pydantic
```

2. Start the server:

```bash
uvicorn app.main:app --reload
```

Server will run at `http://127.0.0.1:8000`.

### API: POST `/think`

- Submit new query:

```bash
curl -s -X POST http://127.0.0.1:8000/think \
  -H 'Content-Type: application/json' \
  -d '{
        "history": [ {"role": "user", "message": "Hello"} ],
        "user_query": "What is the meaning of life?"
      }'
# => { "id": "<uuid>" } (HTTP 202)
```

- Poll for result:

```bash
curl -s -X POST http://127.0.0.1:8000/think \
  -H 'Content-Type: application/json' \
  -d '{ "id": "<uuid-from-previous-response>" }'
# => { "reply": "not ready" } or { "reply": "Response to 'What is the meaning of life?' received." }
```

If the `id` is invalid or expired, the API returns `404` with `{"detail": "Invalid or expired ID"}`.

### Docker

Build the image:

```bash
docker build -t fastapi-async-chatbot .
```

Run the container:

```bash
docker run --rm -p 8000:8000 fastapi-async-chatbot
```

Then use the same curl examples against `http://127.0.0.1:8000/think`.

