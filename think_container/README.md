
# to run locally
docker build -t think-container:latest . && docker run --rm --env-file .env think-container:latest


# to build and push
az acr login --name crvo2gj2ngdhely

container_name=think-container:latest
docker buildx build --platform linux/amd64 -t crvo2gj2ngdhely.azurecr.io/$container_name --no-cache -f Dockerfile .
docker push crvo2gj2ngdhely.azurecr.io/$container_name


# container app env
created resources
- workspace-rgbackendnprfdqy
- think-container-npr

az containerapp env create \
    --name "think-container-npr" \
    --resource-group "rg-backend-npr" \
    --location "West Europe"