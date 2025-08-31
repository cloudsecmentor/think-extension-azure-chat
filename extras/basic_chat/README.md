# Deployment

## Local development

Run from this directory:

```
# build and run
docker compose -f compose.local.yml up --build
```

- Frontend: http://localhost:3000

## Azure Web App for Containers (multi-container)

This app is deployed via GitHub Actions to Azure Web App for Containers using a Docker Compose file `compose.azure.yml` that references images in Azure Container Registry (ACR).

Required GitHub secrets:
- `AZURE_CREDENTIALS` — Azure service principal JSON
- `ACR_NAME` — ACR registry name (e.g. `myregistry`)
- `WEBAPP_NAME` — Azure Web App name

Optional variables (can be set as repo variables or env in workflow):
- `AZ_SUBSCRIPTION_ID` — Azure subscription id
- `AZ_RESOURCE_GROUP` — Azure resource group name
- `AZ_REGION` — Azure region (must match the Web App)

The workflow builds and pushes images, then configures and deploys using the compose file.

