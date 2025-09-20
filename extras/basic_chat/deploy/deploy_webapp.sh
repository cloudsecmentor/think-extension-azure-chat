#!/usr/bin/env bash

set -euo pipefail

# Deploys the Streamlit front-end container to Azure Web App for Containers.
#
# Prereqs:
# - az CLI, docker installed and logged in (az login)
# - Subscription access to the provided subscription
# - App Service Plan (Linux) exists: asp-pd-cmn
#
# Usage:
#   ./deploy_webapp.sh \
#     --app-name think-front \
#     --acr-name <your_acr_name> \
#     [--subscription deedbe27-c01a-42b1-a6b8-c6d1aa432580] \
#     [--resource-group rg-pd-cmn] \
#     [--app-service-plan asp-pd-cmn] \
#     [--image-tag $(date +%Y%m%d%H%M%S)] \
#     [--env-file ../.env] \
#     [--storage-account <storage_account_name>] \
#     [--file-share <file_share_name>] \
#     [--storage-location eastus]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONT_DIR="${SCRIPT_DIR}/../front"

# Defaults from the user's request
SUBSCRIPTION_ID="deedbe27-c01a-42b1-a6b8-c6d1aa432580"
RESOURCE_GROUP="rg-pd-cmn"
APP_SERVICE_PLAN="asp-pd-cmn"
APP_NAME="think-front"
ACR_NAME="acrpdcmn01"
IMAGE_TAG="$(date +%Y%m%d%H%M%S)"
ENV_FILE="${SCRIPT_DIR}/../.env"

# Storage defaults
STORAGE_ACCOUNT="stachatapp01"
FILE_SHARE_NAME="chatdata01"
STORAGE_LOCATION="swedencentral "
STORAGE_SKU="Standard_RAGRS"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --subscription)
      SUBSCRIPTION_ID="$2"; shift 2 ;;
    --resource-group)
      RESOURCE_GROUP="$2"; shift 2 ;;
    --app-service-plan)
      APP_SERVICE_PLAN="$2"; shift 2 ;;
    --app-name)
      APP_NAME="$2"; shift 2 ;;
    --acr-name)
      ACR_NAME="$2"; shift 2 ;;
    --image-tag)
      IMAGE_TAG="$2"; shift 2 ;;
    --env-file)
      ENV_FILE="$2"; shift 2 ;;
    --storage-account)
      STORAGE_ACCOUNT="$2"; shift 2 ;;
    --file-share)
      FILE_SHARE_NAME="$2"; shift 2 ;;
    --storage-location)
      STORAGE_LOCATION="$2"; shift 2 ;;
    -h|--help)
      sed -n '1,120p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

if [[ -z "${ACR_NAME}" ]]; then
  echo "[ERROR] --acr-name is required (name of Azure Container Registry)." >&2
  exit 2
fi

if [[ ! -d "${FRONT_DIR}" ]]; then
  echo "[ERROR] Front-end directory not found at ${FRONT_DIR}" >&2
  exit 3
fi

# Sanitize storage account name constraints: 3-24 chars, lowercase letters and numbers only
SANITIZED_APP_NAME=$(echo -n "${APP_NAME}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9')
if [[ ${#SANITIZED_APP_NAME} -gt 12 ]]; then
  SANITIZED_APP_NAME=${SANITIZED_APP_NAME:0:12}
fi
DEFAULT_STORAGE_ACCOUNT="${SANITIZED_APP_NAME}st"
# If user didn't override the default, use sanitized default
if [[ "${STORAGE_ACCOUNT}" == "thinkfrontst" ]]; then
  STORAGE_ACCOUNT="${DEFAULT_STORAGE_ACCOUNT}"
fi

echo "[INFO] Using subscription: ${SUBSCRIPTION_ID}"
az account set --subscription "${SUBSCRIPTION_ID}"

echo "[INFO] Ensuring resource group exists: ${RESOURCE_GROUP}"
az group show -n "${RESOURCE_GROUP}" >/dev/null 2>&1 || \
  az group create -n "${RESOURCE_GROUP}" -l "${STORAGE_LOCATION}"

echo "[INFO] Ensuring ACR exists: ${ACR_NAME}"
az acr show -n "${ACR_NAME}" -g "${RESOURCE_GROUP}" >/dev/null 2>&1 || \
  az acr create -n "${ACR_NAME}" -g "${RESOURCE_GROUP}" --sku Basic

ACR_LOGIN_SERVER="$(az acr show -n "${ACR_NAME}" -g "${RESOURCE_GROUP}" --query loginServer -o tsv)"
ACR_ID="$(az acr show -n "${ACR_NAME}" -g "${RESOURCE_GROUP}" --query id -o tsv)"
IMAGE_NAME="${ACR_LOGIN_SERVER}/${APP_NAME}:${IMAGE_TAG}"

# Ensure Storage Account and File Share for persistent /data
echo "[INFO] Ensuring Storage Account exists: ${STORAGE_ACCOUNT} (location=${STORAGE_LOCATION})"
az storage account show -n "${STORAGE_ACCOUNT}" -g "${RESOURCE_GROUP}" >/dev/null 2>&1 || \
  az storage account create -n "${STORAGE_ACCOUNT}" -g "${RESOURCE_GROUP}" -l "${STORAGE_LOCATION}" --sku "${STORAGE_SKU}" >/dev/null

STORAGE_KEY="$(az storage account keys list -n "${STORAGE_ACCOUNT}" -g "${RESOURCE_GROUP}" --query "[0].value" -o tsv)"
if [[ -z "${STORAGE_KEY}" ]]; then
  echo "[ERROR] Could not retrieve storage account key for ${STORAGE_ACCOUNT}" >&2
  exit 8
fi

echo "[INFO] Ensuring Azure File Share exists: ${FILE_SHARE_NAME}"
az storage share-rm show --storage-account "${STORAGE_ACCOUNT}" --name "${FILE_SHARE_NAME}" >/dev/null 2>&1 || \
  az storage share create --name "${FILE_SHARE_NAME}" --account-name "${STORAGE_ACCOUNT}" --account-key "${STORAGE_KEY}" >/dev/null

# Build and push image
echo "[INFO] Building Docker image: ${IMAGE_NAME}"
docker build -t "${IMAGE_NAME}" "${FRONT_DIR}"

echo "[INFO] Logging into ACR: ${ACR_NAME}"
az acr login -n "${ACR_NAME}"

echo "[INFO] Pushing image to ACR"
docker push "${IMAGE_NAME}"

echo "[INFO] Checking App Service Plan: ${APP_SERVICE_PLAN} in ${RESOURCE_GROUP}"
if ! az appservice plan show -n "${APP_SERVICE_PLAN}" -g "${RESOURCE_GROUP}" >/dev/null 2>&1; then
  echo "[ERROR] App Service Plan '${APP_SERVICE_PLAN}' not found in resource group '${RESOURCE_GROUP}'." >&2
  echo "        Details:" >&2
  az appservice plan show -n "${APP_SERVICE_PLAN}" -g "${RESOURCE_GROUP}" || true
  exit 4
fi

# Verify it's a Linux plan
PLAN_RESERVED="$(az appservice plan show -n "${APP_SERVICE_PLAN}" -g "${RESOURCE_GROUP}" --query reserved -o tsv)"
if [[ -z "${PLAN_RESERVED}" ]]; then
  # Fallback: check kind contains linux (portable to older Bash)
  PLAN_KIND_STR="$(az appservice plan show -n "${APP_SERVICE_PLAN}" -g "${RESOURCE_GROUP}" --query kind -o tsv)"
  PLAN_KIND_STR_LOWER="$(printf "%s" "${PLAN_KIND_STR}" | tr '[:upper:]' '[:lower:]')"
  if [[ "${PLAN_KIND_STR_LOWER}" != *linux* ]]; then
    echo "[ERROR] App Service Plan '${APP_SERVICE_PLAN}' is not Linux (kind='${PLAN_KIND_STR}')." >&2
    exit 5
  fi
else
  if [[ "${PLAN_RESERVED}" != "true" ]]; then
    echo "[ERROR] App Service Plan '${APP_SERVICE_PLAN}' is not Linux (reserved=${PLAN_RESERVED})." >&2
    exit 5
  fi
fi

echo "[INFO] Creating or updating Web App: ${APP_NAME}"
if az webapp show -n "${APP_NAME}" -g "${RESOURCE_GROUP}" >/dev/null 2>&1; then
  echo "[INFO] Web App exists."
else
  az webapp create \
    -g "${RESOURCE_GROUP}" \
    -p "${APP_SERVICE_PLAN}" \
    -n "${APP_NAME}" \
    --runtime "PYTHON:3.11"
fi

# Mount Azure File Share at /data
echo "[INFO] Mounting Azure File Share '${FILE_SHARE_NAME}' at /data on Web App"
az webapp config storage-account add \
  -g "${RESOURCE_GROUP}" -n "${APP_NAME}" \
  --custom-id data \
  --storage-type AzureFiles \
  --account-name "${STORAGE_ACCOUNT}" \
  --share-name "${FILE_SHARE_NAME}" \
  --access-key "${STORAGE_KEY}" \
  --mount-path /data >/dev/null

echo "[INFO] Enabling system-assigned managed identity on Web App"
az webapp identity assign -g "${RESOURCE_GROUP}" -n "${APP_NAME}" >/dev/null
PRINCIPAL_ID="$(az webapp identity show -g "${RESOURCE_GROUP}" -n "${APP_NAME}" --query principalId -o tsv)"
if [[ -z "${PRINCIPAL_ID}" || "${PRINCIPAL_ID}" == "null" ]]; then
  echo "[ERROR] Failed to enable managed identity on the Web App (principalId empty)." >&2
  exit 6
fi

echo "[INFO] Ensuring 'AcrPull' role assignment exists for Web App identity on ACR"
# Create (ignore conflict) then poll for existence to handle ARM propagation
set +e
az role assignment create \
  --assignee-object-id "${PRINCIPAL_ID}" \
  --assignee-principal-type ServicePrincipal \
  --role AcrPull \
  --scope "${ACR_ID}" 
#   --scope "${ACR_ID}" >/dev/null 2>&1 || true

# for i in {1..18}; do
#   ASSIGN_ID="$(az role assignment list \
#     --assignee-object-id "${PRINCIPAL_ID}" \
#     --scope "${ACR_ID}" \
#     --role AcrPull \
#     --query "[0].id" -o tsv 2>/dev/null)"
#   if [[ -n "${ASSIGN_ID}" ]]; then
#     echo "[INFO] AcrPull role assignment detected."
#     break
#   fi
#   echo "[WARN] Role assignment not yet visible, waiting 10s ($i/18) ..."
#   sleep 10
# done
# set -e

# if [[ -z "${ASSIGN_ID:-}" ]]; then
#   echo "[ERROR] AcrPull role assignment did not appear after waiting. Please retry later." >&2
#   exit 7
# fi

echo "[INFO] Configuring Web App to run main container via Sidecar API (isMain=true)"
APP_ID="$(az webapp show --resource-group "${RESOURCE_GROUP}" --name "${APP_NAME}" --query id -o tsv)"
API_VER=2023-12-01

az rest --method PUT \
  --url "https://management.azure.com${APP_ID}/sitecontainers/front?api-version=${API_VER}" \
  --body @- <<JSON
{
  "name": "front",
  "properties": {
    "image": "${IMAGE_NAME}",
    "isMain": true,
    "targetPort": 8501,
    "inheritAppSettingsAndConnectionStrings": true,
    "authType": "SystemIdentity"
  }
}
JSON

echo "[INFO] Switching Web App to Sidecar mode"
az webapp config set --resource-group "${RESOURCE_GROUP}" --name "${APP_NAME}" --linux-fx-version "sitecontainers" >/dev/null

echo "[INFO] Applying application settings (including WEBSITES_PORT=8501 and CHAT_DB_PATH)"
SETTINGS=(WEBSITES_PORT=8501 CHAT_DB_PATH=/data/chat.db)
if [[ -f "${ENV_FILE}" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    # skip comments and empty lines
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    # only accept KEY=VALUE
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      SETTINGS+=("$line")
    fi
  done < "${ENV_FILE}"
else
  echo "[WARN] .env file not found at ${ENV_FILE}. Continuing without additional app settings."
fi

az webapp config appsettings set \
  -g "${RESOURCE_GROUP}" -n "${APP_NAME}" \
  --settings "${SETTINGS[@]}" >/dev/null

echo "[INFO] Restarting Web App"
az webapp restart -g "${RESOURCE_GROUP}" -n "${APP_NAME}" >/dev/null

APP_URL="https://${APP_NAME}.azurewebsites.net"
echo "[SUCCESS] Deployment complete: ${APP_URL}"

