
# to run locally
docker build -t think-container:latest . && docker run --rm --env-file .env think-container:latest


# to build and push
``` bash
# TO START DOCKER DEAMON
# colima start
acrname=""
imagename=""
az acr login --name $acrname
docker buildx build --platform linux/amd64 -t $acrname.azurecr.io/$imagename:latest --no-cache -f Dockerfile .
docker push $acrname.azurecr.io/$imagename:latest

```


# container app env
az containerapp env create \
    --name "app_env_name" \
    --resource-group "rg-name" \
    --location "West Europe"