## Azure AI Foundry FastAPI service

### Prerequisites
- Python 3.10+
- Azure login available to `DefaultAzureCredential`
- Connection string for the Azure AI Foundry project (optional, can use default)

### Setup
1. Create and activate a virtual environment (recommended).
2. Install requirements (from this directory):
```bash
pip install -r requirements.txt
```

### Configuration
- Optionally set the connection string used by the service:
```bash
export AZURE_AI_FOUNDRY_CONN_STR="<region>.api.azureml.ms;<subscription-or-workspace-id>;<resource-group>;<project-name>"
```
- Ensure `DefaultAzureCredential` can authenticate (Azure CLI login, Managed Identity, or environment variables).

### Run locally (from this directory)
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

### Docker (from this directory)
Build image:
```bash
docker build -t aifoundry-fastapi .
```

Run container:
```bash
docker run --rm -p 8000:8000 \
  -e AZURE_AI_FOUNDRY_CONN_STR="$AZURE_AI_FOUNDRY_CONN_STR" \
  -e AZURE_CLIENT_ID="$AZURE_CLIENT_ID" \
  -e AZURE_TENANT_ID="$AZURE_TENANT_ID" \
  -e AZURE_CLIENT_SECRET="$AZURE_CLIENT_SECRET" \
  aifoundry-fastapi

docker run --rm -p 8000:8000 -it aifoundry-fastapi

```

```bash
# TO START DOCKER DEAMON
# colima start
acrname=""
imagename=""
az acr login --name $acrname
docker buildx build --platform linux/amd64 -t $acrname.azurecr.io/$imagename:latest --no-cache -f Dockerfile .
docker push $acrname.azurecr.io/$imagename:latest



```


Notes:
- If using Azure CLI-based auth locally, prefer a service principal for Docker.
- Ensure container network access to Azure endpoints.

### Endpoints
- `GET /health` — health check
- `POST /message` — body: `{ "content": "your text" }`; returns the first message from `messages.text_messages`.

### Example request
```bash
curl -s -X POST \
  http://127.0.0.1:8000/message \
  -H 'Content-Type: application/json' \
  -d '{"content":"Hello from FastAPI"}' | jq
```


