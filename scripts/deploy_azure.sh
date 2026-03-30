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

BACKEND_IMAGE="ghcr.io/${GHCR_USERNAME}/rag-backend:latest"
FRONTEND_IMAGE="ghcr.io/${GHCR_USERNAME}/rag-frontend:latest"

echo "Buildear imágenes localmente con Docker..."
docker build -t "$BACKEND_IMAGE" "$ROOT_DIR/backend"
docker build -t "$FRONTEND_IMAGE" \
  --build-arg VITE_API_URL="https://$API_SUBDOMAIN" \
  "$ROOT_DIR/frontend"

echo "Authenticando en GitHub Container Registry..."
echo "Para pushear a ghcr.io, necesitas:"
echo "  1. Un Personal Access Token de GitHub con permiso 'write:packages'"
echo "  2. Ejecutar: echo <PAT> | docker login ghcr.io -u <username> --password-stdin"
echo ""
read -p "¿Ya has autenticado en ghcr.io con 'docker login'? (s/n): " auth_check
if [[ "$auth_check" != "s" && "$auth_check" != "S" ]]; then
  echo "Por favor, autentica en ghcr.io primero:"
  docker login ghcr.io
fi

echo "Pusheando imágenes a GitHub Container Registry..."
docker push "$BACKEND_IMAGE"
docker push "$FRONTEND_IMAGE"

echo "Imágenes pusheadas correctamente a ghcr.io"

echo ""
echo "⚠️  PRÓXIMOS PASOS MANUALES:"
echo "1. Configura Azure Container Apps para usar las imágenes:"
echo "   - Backend:  $BACKEND_IMAGE"
echo "   - Frontend: $FRONTEND_IMAGE"
echo ""
echo "2. En Azure Portal, configura las siguientes variables de entorno para el backend:"
echo "   - GOOGLE_API_KEY=$GOOGLE_API_KEY"
echo "   - CONTACT_EMAILS=$CONTACT_EMAILS"
echo "   - PROFESSIONAL_LINKEDIN=$PROFESSIONAL_LINKEDIN"
echo "   - ADMIN_READ_KEY=$ADMIN_READ_KEY"
echo "   - TURNSTILE_SECRET_KEY=$TURNSTILE_SECRET_KEY"
echo "   (Según corresponda: OPENAI_* o AZURE_OPENAI_*)"
echo ""
echo "3. Redeploy las apps en Azure Container Apps"
echo ""
echo "✓ Script de build completado. Procede con la configuración manual en Azure."
