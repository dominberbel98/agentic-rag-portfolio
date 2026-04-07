#!/usr/bin/env bash
set -euo pipefail

# Deploys backend + frontend to Azure Container Apps using GitHub Container Registry (ghcr.io).

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
  AZ_CONTAINERAPPS_ENV AZ_BACKEND_APP AZ_FRONTEND_APP
  API_SUBDOMAIN CONTACT_EMAILS PROFESSIONAL_LINKEDIN ADMIN_READ_KEY
  MAX_REQUESTS_PER_MINUTE_PER_IP MAX_TOKENS_PER_DAY
  GOOGLE_API_KEY GHCR_USERNAME
)

BACKEND_MIN_REPLICAS="${BACKEND_MIN_REPLICAS:-1}"
BACKEND_MAX_REPLICAS="${BACKEND_MAX_REPLICAS:-2}"
FRONTEND_MIN_REPLICAS="${FRONTEND_MIN_REPLICAS:-1}"
FRONTEND_MAX_REPLICAS="${FRONTEND_MAX_REPLICAS:-2}"
IMAGE_TAG="${IMAGE_TAG:-$(date -u +%Y%m%d%H%M%S)}"

for var in "${required[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "Variable requerida vacia: $var"
    exit 1
  fi
done

resolve_ghcr_token() {
  if [[ -n "${GHCR_TOKEN:-}" ]]; then
    printf '%s' "$GHCR_TOKEN"
    return 0
  fi

  if command -v docker-credential-desktop.exe >/dev/null 2>&1; then
    printf 'ghcr.io' | docker-credential-desktop.exe get | python3 -c "import json,sys; print(json.load(sys.stdin)['Secret'])"
    return 0
  fi

  if command -v docker-credential-desktop >/dev/null 2>&1; then
    printf 'ghcr.io' | docker-credential-desktop get | python3 -c "import json,sys; print(json.load(sys.stdin)['Secret'])"
    return 0
  fi

  echo "No se pudo resolver GHCR_TOKEN. Define GHCR_TOKEN o haz docker login ghcr.io con un helper compatible." >&2
  return 1
}

GHCR_TOKEN_RESOLVED="$(resolve_ghcr_token)"

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
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
echo "Esperando que se registren los providers (puede tardar 1-2 minutos)..."
sleep 30

az group create --name "$AZ_RESOURCE_GROUP" --location "$AZ_LOCATION"

echo "Registrando extensión de Container Apps..."
az extension add --name containerapp --upgrade

echo "Creando Container Apps Environment..."
if ! az containerapp env show --name "$AZ_CONTAINERAPPS_ENV" --resource-group "$AZ_RESOURCE_GROUP" >/dev/null 2>&1; then
  az containerapp env create \
    --name "$AZ_CONTAINERAPPS_ENV" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --location "$AZ_LOCATION"
fi

BACKEND_IMAGE="ghcr.io/${GHCR_USERNAME}/rag-backend:${IMAGE_TAG}"
FRONTEND_IMAGE="ghcr.io/${GHCR_USERNAME}/rag-frontend:${IMAGE_TAG}"
BACKEND_IMAGE_LATEST="ghcr.io/${GHCR_USERNAME}/rag-backend:latest"
FRONTEND_IMAGE_LATEST="ghcr.io/${GHCR_USERNAME}/rag-frontend:latest"

echo "Buildear imágenes localmente con Docker..."
docker build -t "$BACKEND_IMAGE" "$ROOT_DIR/backend"
docker tag "$BACKEND_IMAGE" "$BACKEND_IMAGE_LATEST"
docker build -t "$FRONTEND_IMAGE" \
  --build-arg VITE_API_URL="https://$API_SUBDOMAIN" \
  "$ROOT_DIR/frontend"
docker tag "$FRONTEND_IMAGE" "$FRONTEND_IMAGE_LATEST"

echo "Autenticando en GitHub Container Registry..."
echo "$GHCR_TOKEN_RESOLVED" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin

echo "Pusheando imágenes a GitHub Container Registry..."
docker push "$BACKEND_IMAGE"
docker push "$BACKEND_IMAGE_LATEST"
docker push "$FRONTEND_IMAGE"
docker push "$FRONTEND_IMAGE_LATEST"

echo "Imágenes pusheadas correctamente a ghcr.io"

echo "Configurando GHCR en Azure Container Apps..."
az containerapp registry set \
  --name "$AZ_BACKEND_APP" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --server ghcr.io \
  --username "$GHCR_USERNAME" \
  --password "$GHCR_TOKEN_RESOLVED"

az containerapp registry set \
  --name "$AZ_FRONTEND_APP" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --server ghcr.io \
  --username "$GHCR_USERNAME" \
  --password "$GHCR_TOKEN_RESOLVED"

echo "Actualizando imágenes en Azure Container Apps..."
az containerapp update \
  --name "$AZ_BACKEND_APP" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --image "$BACKEND_IMAGE" \
  --min-replicas "$BACKEND_MIN_REPLICAS" \
  --max-replicas "$BACKEND_MAX_REPLICAS"

az containerapp update \
  --name "$AZ_FRONTEND_APP" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --image "$FRONTEND_IMAGE" \
  --min-replicas "$FRONTEND_MIN_REPLICAS" \
  --max-replicas "$FRONTEND_MAX_REPLICAS"

echo "Eliminando referencia antigua a ACR si existe..."
az containerapp registry remove \
  --name "$AZ_BACKEND_APP" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --server acrdomingorag.azurecr.io || true

az containerapp registry remove \
  --name "$AZ_FRONTEND_APP" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --server acrdomingorag.azurecr.io || true

echo "✓ Redeploy completado"
echo "  Backend image:  $BACKEND_IMAGE"
echo "  Frontend image: $FRONTEND_IMAGE"
