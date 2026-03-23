#!/usr/bin/env bash
set -euo pipefail

# Deploys backend + frontend to Azure Container Apps using images in ACR.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$ROOT_DIR/infra/aca/azure.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Falta $ENV_FILE (copia infra/aca/azure.env.example)."
  exit 1
fi

source "$ENV_FILE"

required=(
  AZ_LOCATION AZ_RESOURCE_GROUP AZ_SUBSCRIPTION_ID
  AZ_ACR_NAME AZ_CONTAINERAPPS_ENV AZ_BACKEND_APP AZ_FRONTEND_APP
  API_SUBDOMAIN CONTACT_EMAILS PROFESSIONAL_LINKEDIN ADMIN_READ_KEY
  MAX_REQUESTS_PER_MINUTE_PER_IP MAX_TOKENS_PER_DAY
  AZURE_SEARCH_ENDPOINT AZURE_SEARCH_API_KEY AZURE_SEARCH_INDEX_NAME
)

BACKEND_MIN_REPLICAS="${BACKEND_MIN_REPLICAS:-1}"
BACKEND_MAX_REPLICAS="${BACKEND_MAX_REPLICAS:-2}"
FRONTEND_MIN_REPLICAS="${FRONTEND_MIN_REPLICAS:-1}"
FRONTEND_MAX_REPLICAS="${FRONTEND_MAX_REPLICAS:-2}"

for var in "${required[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "Variable requerida vacia: $var"
    exit 1
  fi
done

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  if [[ -z "${OPENAI_MODEL:-}" ]]; then
    echo "Variable requerida vacia: OPENAI_MODEL (cuando se usa OPENAI_API_KEY)"
    exit 1
  fi
elif [[ -z "${AZURE_OPENAI_ENDPOINT:-}" || -z "${AZURE_OPENAI_API_KEY:-}" || -z "${AZURE_OPENAI_CHAT_DEPLOYMENT:-}" ]]; then
  echo "Debes configurar OpenAI directo (OPENAI_API_KEY + OPENAI_MODEL) o Azure OpenAI completo."
  exit 1
fi

az account set --subscription "$AZ_SUBSCRIPTION_ID"

echo "Registrando providers necesarios..."
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
echo "Esperando que se registren los providers (puede tardar 1-2 minutos)..."
sleep 30

az group create --name "$AZ_RESOURCE_GROUP" --location "$AZ_LOCATION"

az acr create \
  --name "$AZ_ACR_NAME" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --sku Basic \
  --admin-enabled true

ACR_LOGIN_SERVER="$(az acr show --name "$AZ_ACR_NAME" --resource-group "$AZ_RESOURCE_GROUP" --query loginServer -o tsv)"

echo "Registrando extensión de Container Apps..."
az extension add --name containerapp --upgrade

echo "Creando Container Apps Environment..."
if ! az containerapp env show --name "$AZ_CONTAINERAPPS_ENV" --resource-group "$AZ_RESOURCE_GROUP" >/dev/null 2>&1; then
  az containerapp env create \
    --name "$AZ_CONTAINERAPPS_ENV" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --location "$AZ_LOCATION"
fi

echo "Buildear imágenes localmente con Docker..."
docker build -t "$ACR_LOGIN_SERVER/rag-backend:latest" "$ROOT_DIR/backend"
docker build -t "$ACR_LOGIN_SERVER/rag-frontend:latest" \
  --build-arg VITE_API_URL="https://$API_SUBDOMAIN" \
  "$ROOT_DIR/frontend"

echo "Login a ACR..."
# Usar az acr login evita almacenar credenciales admin en variables de shell
az acr login --name "$AZ_ACR_NAME"
# Las credenciales admin siguen siendo necesarias para el pull que hace Container Apps.
# TODO: migrar a managed identity para eliminar del todo el admin user de ACR:
#   1. Quitar --admin-enabled true del az acr create
#   2. Añadir --assign-identity [system] al az containerapp create
#   3. Otorgar rol AcrPull a cada managed identity sobre el ACR
#   4. Eliminar --registry-username/password de los comandos containerapp
ACR_USER="$(az acr credential show --name "$AZ_ACR_NAME" --query username -o tsv)"
ACR_PASS="$(az acr credential show --name "$AZ_ACR_NAME" --query passwords[0].value -o tsv)"

echo "Pusheando imágenes a ACR..."
docker push "$ACR_LOGIN_SERVER/rag-backend:latest"
docker push "$ACR_LOGIN_SERVER/rag-frontend:latest"

echo "Imágenes pusheadas correctamente"

if ! az containerapp show --name "$AZ_BACKEND_APP" --resource-group "$AZ_RESOURCE_GROUP" >/dev/null 2>&1; then
  az containerapp create \
    --name "$AZ_BACKEND_APP" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --environment "$AZ_CONTAINERAPPS_ENV" \
    --ingress external \
    --target-port 8000 \
    --min-replicas "$BACKEND_MIN_REPLICAS" \
    --max-replicas "$BACKEND_MAX_REPLICAS" \
    --image "$ACR_LOGIN_SERVER/rag-backend:latest" \
    --registry-server "$ACR_LOGIN_SERVER" \
    --registry-username "$ACR_USER" \
    --registry-password "$ACR_PASS" \
    --env-vars \
      APP_ENV=prod \
      CORS_ORIGINS="https://$WEB_SUBDOMAIN" \
      CONTACT_EMAILS="$CONTACT_EMAILS" \
      PROFESSIONAL_LINKEDIN="$PROFESSIONAL_LINKEDIN" \
      ADMIN_READ_KEY="$ADMIN_READ_KEY" \
      SHOW_CITATIONS=false \
      MAX_REQUESTS_PER_MINUTE_PER_IP="$MAX_REQUESTS_PER_MINUTE_PER_IP" \
      MAX_TOKENS_PER_DAY="$MAX_TOKENS_PER_DAY" \
      TURNSTILE_SECRET_KEY="${TURNSTILE_SECRET_KEY:-}" \
      OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
      OPENAI_MODEL="${OPENAI_MODEL:-}" \
      AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
      AZURE_OPENAI_API_KEY="$AZURE_OPENAI_API_KEY" \
      AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2024-10-21}" \
      AZURE_OPENAI_CHAT_DEPLOYMENT="$AZURE_OPENAI_CHAT_DEPLOYMENT" \
      AZURE_SEARCH_ENDPOINT="$AZURE_SEARCH_ENDPOINT" \
      AZURE_SEARCH_API_KEY="$AZURE_SEARCH_API_KEY" \
      AZURE_SEARCH_INDEX_NAME="$AZURE_SEARCH_INDEX_NAME"
else
  az containerapp update \
    --name "$AZ_BACKEND_APP" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/rag-backend:latest" \
    --min-replicas "$BACKEND_MIN_REPLICAS" \
    --max-replicas "$BACKEND_MAX_REPLICAS" \
    --set-env-vars \
      APP_ENV=prod \
      CORS_ORIGINS="https://$WEB_SUBDOMAIN" \
      CONTACT_EMAILS="$CONTACT_EMAILS" \
      PROFESSIONAL_LINKEDIN="$PROFESSIONAL_LINKEDIN" \
      ADMIN_READ_KEY="$ADMIN_READ_KEY" \
      SHOW_CITATIONS=false \
      MAX_REQUESTS_PER_MINUTE_PER_IP="$MAX_REQUESTS_PER_MINUTE_PER_IP" \
      MAX_TOKENS_PER_DAY="$MAX_TOKENS_PER_DAY" \
      TURNSTILE_SECRET_KEY="${TURNSTILE_SECRET_KEY:-}" \
      OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
      OPENAI_MODEL="${OPENAI_MODEL:-}" \
      AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
      AZURE_OPENAI_API_KEY="$AZURE_OPENAI_API_KEY" \
      AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2024-10-21}" \
      AZURE_OPENAI_CHAT_DEPLOYMENT="$AZURE_OPENAI_CHAT_DEPLOYMENT" \
      AZURE_SEARCH_ENDPOINT="$AZURE_SEARCH_ENDPOINT" \
      AZURE_SEARCH_API_KEY="$AZURE_SEARCH_API_KEY" \
      AZURE_SEARCH_INDEX_NAME="$AZURE_SEARCH_INDEX_NAME"
fi

BACKEND_FQDN="$(az containerapp show --name "$AZ_BACKEND_APP" --resource-group "$AZ_RESOURCE_GROUP" --query properties.configuration.ingress.fqdn -o tsv)"

if ! az containerapp show --name "$AZ_FRONTEND_APP" --resource-group "$AZ_RESOURCE_GROUP" >/dev/null 2>&1; then
  az containerapp create \
    --name "$AZ_FRONTEND_APP" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --environment "$AZ_CONTAINERAPPS_ENV" \
    --ingress external \
    --target-port 80 \
    --min-replicas "$FRONTEND_MIN_REPLICAS" \
    --max-replicas "$FRONTEND_MAX_REPLICAS" \
    --image "$ACR_LOGIN_SERVER/rag-frontend:latest" \
    --registry-server "$ACR_LOGIN_SERVER" \
    --registry-username "$ACR_USER" \
    --registry-password "$ACR_PASS"
else
  az containerapp update \
    --name "$AZ_FRONTEND_APP" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/rag-frontend:latest" \
    --min-replicas "$FRONTEND_MIN_REPLICAS" \
    --max-replicas "$FRONTEND_MAX_REPLICAS"
fi

FRONTEND_FQDN="$(az containerapp show --name "$AZ_FRONTEND_APP" --resource-group "$AZ_RESOURCE_GROUP" --query properties.configuration.ingress.fqdn -o tsv)"

echo "Backend FQDN: $BACKEND_FQDN"
echo "Frontend FQDN: $FRONTEND_FQDN"

echo "Siguiente paso: configurar dominio custom en ambas apps (ver README)."
