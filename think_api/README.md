## Azure AI Think — FastAPI service

### Overview
Simple FastAPI service that writes a chat message document to Azure Cosmos DB. It exposes:
- `GET /healthz` — health check
- `POST /messages` — accepts JSON body `{ "threadId": "..." }` and inserts a document

### Prerequisites
- Python 3.10+
- Azure Cosmos DB account and container

### Configuration (.env)
Create a `.env` file in this directory (or any parent dir) with:
```bash
AZURE_COSMOSDB_URI=...               # e.g. https://<account>.documents.azure.com:443/
AZURE_COSMOSDB_DB_NAME=...
AZURE_COSMOSDB_CONTAINER_NAME=...
AZURE_COSMOSDB_KEY=...
```

Note: The code uses `threadId` as the partition key. Ensure your container partition key path is `/threadId` (or adjust the code to match your container).

### Local run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker

Build the image:
```bash

# TO START DOCKER DEAMON
# colima start

docker build -t think-api:latest .
```

Run with env from `.env`:
```bash
docker build -t think-api:latest . && docker run --rm -p 8000:8000 --env-file .env think-api:latest


docker run --rm -p 8000:8000 --env-file .env think-api:latest
```

### API
Health:
```bash
curl -s http://127.0.0.1:8000/healthz | jq
```

Create message:
```bash
curl -s -X POST \
  http://127.0.0.1:8000/messages \
  -H 'Content-Type: application/json' \
  -d '{"threadId":"abc123"}' | jq
```

### Inserted document shape
```json
{
  "id": "<uuid>",
  "type": "CHAT_MESSAGE",
  "content": "this is a test text",
  "name": "BingSearch",
  "role": "function",
  "threadId": "<your-threadId>"
}
```