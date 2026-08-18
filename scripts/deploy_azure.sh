#!/usr/bin/env bash
set -euo pipefail

# Deploys the backend to Azure Container Apps (image via ghcr.io) and the
# frontend to Azure Static Web Apps.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$ROOT_DIR/infra/aca/azure.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Falta $ENV_FILE (copia infra/aca/azure.env.example)."
  exit 1
fi

# ── The frontend has two publishers, and this one does not win ───────────────
#
# .github/workflows/update-laliga.yml rebuilds the frontend from origin/main and
# redeploys it to Static Web Apps every 30 minutes. So a deploy from this script
# whose commits are not pushed is silently reverted within half an hour: the cron
# checks out origin/main, builds the older code and publishes it over the top.
#
# That happened on 2026-08-18. The site served a frontend from before the deploy
# while the backend was current, and nothing reported an error, because from
# Azure's point of view both deployments succeeded.
#
# Pushing first is therefore not tidiness, it is a requirement. Refuse rather
# than warn: a warning scrolls past in a log nobody reads.
if git -C "$ROOT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  git -C "$ROOT_DIR" fetch origin main --quiet 2>/dev/null || true

  if ! git -C "$ROOT_DIR" diff --quiet HEAD -- ':!frontend/public/data'; then
    echo "ERROR: hay cambios sin commitear. El cron de La Liga desplegaría origin/main"
    echo "       por encima de este despliegue en menos de 30 minutos."
    git -C "$ROOT_DIR" status --short -- ':!frontend/public/data' | sed 's/^/       /'
    exit 1
  fi

  UNPUSHED="$(git -C "$ROOT_DIR" rev-list --count origin/main..HEAD 2>/dev/null || echo 0)"
  if [[ "$UNPUSHED" -gt 0 ]]; then
    echo "ERROR: $UNPUSHED commit(s) sin subir a origin/main."
    git -C "$ROOT_DIR" log --oneline origin/main..HEAD | sed 's/^/       /'
    echo
    echo "       El workflow update-laliga.yml recompila el frontend desde origin/main"
    echo "       cada 30 minutos, así que este despliegue se revertiría solo."
    echo "       Ejecuta:  git push origin main"
    exit 1
  fi
  echo "OK: el árbol está limpio y sincronizado con origin/main."
fi

source "$ENV_FILE"

required=(
  AZ_LOCATION AZ_RESOURCE_GROUP AZ_SUBSCRIPTION_ID
  AZ_CONTAINERAPPS_ENV AZ_BACKEND_APP AZ_STATIC_WEB_APP
  API_SUBDOMAIN WEB_SUBDOMAIN CONTACT_EMAILS PROFESSIONAL_LINKEDIN ADMIN_READ_KEY
  MAX_REQUESTS_PER_MINUTE_PER_IP MAX_TOKENS_PER_DAY
  GOOGLE_API_KEY GHCR_USERNAME
)

BACKEND_MIN_REPLICAS="${BACKEND_MIN_REPLICAS:-1}"
BACKEND_MAX_REPLICAS="${BACKEND_MAX_REPLICAS:-2}"
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
az provider register --namespace Microsoft.Web
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
BACKEND_IMAGE_LATEST="ghcr.io/${GHCR_USERNAME}/rag-backend:latest"

# Both files must be inside backend/ — that is the Docker build context. The
# Dockerfile globs them so a missing file does not fail the build, which means an
# image without them starts fine and silently answers without grounding.
if [[ ! -f "$ROOT_DIR/backend/embeddings_cache.json" ]]; then
  echo "Falta backend/embeddings_cache.json. Ejecuta primero:"
  echo "  python scripts/build_kb.py && python scripts/index_documents.py"
  exit 1
fi
if [[ ! -f "$ROOT_DIR/backend/vocabulary.json" ]]; then
  echo "Falta backend/vocabulary.json (guarda contra alucinaciones). Ejecuta primero:"
  echo "  python scripts/build_kb.py"
  exit 1
fi

echo "Buildear imagen backend con Docker..."
docker build -t "$BACKEND_IMAGE" "$ROOT_DIR/backend"
docker tag "$BACKEND_IMAGE" "$BACKEND_IMAGE_LATEST"

echo "Autenticando en GitHub Container Registry..."
echo "$GHCR_TOKEN_RESOLVED" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin

echo "Pusheando imagen backend a GitHub Container Registry..."
docker push "$BACKEND_IMAGE"
docker push "$BACKEND_IMAGE_LATEST"

echo "Buildear frontend con npm..."
cd "$ROOT_DIR/frontend"
npm ci --silent
VITE_API_URL="https://$API_SUBDOMAIN" \
VITE_TURNSTILE_SITE_KEY="$TURNSTILE_SITE_KEY" \
npm run build
cd "$ROOT_DIR"

echo "Imagen backend pusheada correctamente a ghcr.io"

echo "Configurando GHCR en Azure Container Apps (backend)..."
az containerapp registry set \
  --name "$AZ_BACKEND_APP" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --server ghcr.io \
  --username "$GHCR_USERNAME" \
  --password "$GHCR_TOKEN_RESOLVED"

echo "Actualizando imagen backend en Azure Container Apps..."

# ── Credentials ──────────────────────────────────────────────────────────────
#
# Every credential goes in as a Container Apps SECRET and is referenced with
# secretref:. This script previously passed them as plaintext literals to
# --set-env-vars, which made them readable by anyone with Reader on the
# subscription and visible in `az containerapp show` output and ARM exports.
# It also means running this script must not silently undo that: a literal here
# would overwrite the secretref and re-expose the value.

echo "Cargando credenciales como secrets de Container Apps..."
SECRET_ARGS=()
add_secret() {           # add_secret <secret-name> <value>
  # The `return 0` is load-bearing. As a bare `[[ -n ... ]] && ...` list, this
  # function returned 1 whenever the value was empty, and under `set -e` that
  # killed the deploy on the spot — silently, because the test prints nothing.
  # TURNSTILE_SECRET_KEY is deliberately empty (captcha is disabled), so every
  # run died here: after building the image, pushing it to GHCR and pointing the
  # registry at it, but before updating the container. The deploy looked like it
  # had worked and the app kept serving the previous revision, which is how the
  # live configuration and infra/aca/azure.env drifted apart.
  [[ -n "${2:-}" ]] && SECRET_ARGS+=("$1=$2")
  return 0
}
add_secret openai-api-key "${OPENAI_API_KEY:-}"
add_secret google-api-key "${GOOGLE_API_KEY:-}"
add_secret admin-read-key "${ADMIN_READ_KEY:-}"
add_secret turnstile-secret-key "${TURNSTILE_SECRET_KEY:-}"
# FUTBOARD talks to Neon. Optional: leaving it unset ships a backend whose
# FUTBOARD endpoints answer 503 while everything else works normally.
add_secret futboard-database-url "${FUTBOARD_DATABASE_URL:-}"

if [[ ${#SECRET_ARGS[@]} -gt 0 ]]; then
  az containerapp secret set \
    --name "$AZ_BACKEND_APP" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --secrets "${SECRET_ARGS[@]}" \
    --output none
fi

# Non-sensitive configuration only.
BACKEND_ENV_VARS=(
  "APP_ENV=${APP_ENV:-production}"
  "CORS_ORIGINS=${CORS_ORIGINS:-https://domingoberbel.com,https://www.domingoberbel.com}"
  "CONTACT_EMAILS=${CONTACT_EMAILS}"
  "PROFESSIONAL_LINKEDIN=${PROFESSIONAL_LINKEDIN}"
  "MAX_REQUESTS_PER_MINUTE_PER_IP=${MAX_REQUESTS_PER_MINUTE_PER_IP}"
  "MAX_TOKENS_PER_DAY=${MAX_TOKENS_PER_DAY}"
  "OPENAI_MODEL=${OPENAI_MODEL:-gpt-5.6-luna}"
  "EMBEDDING_MODEL=${EMBEDDING_MODEL:-gemini-embedding-2}"
)

# Secrets by reference, never by value.
[[ -n "${OPENAI_API_KEY:-}" ]] && BACKEND_ENV_VARS+=("OPENAI_API_KEY=secretref:openai-api-key")
[[ -n "${GOOGLE_API_KEY:-}" ]] && BACKEND_ENV_VARS+=("GOOGLE_API_KEY=secretref:google-api-key")
[[ -n "${ADMIN_READ_KEY:-}" ]] && BACKEND_ENV_VARS+=("ADMIN_READ_KEY=secretref:admin-read-key")
[[ -n "${TURNSTILE_SECRET_KEY:-}" ]] && \
  BACKEND_ENV_VARS+=("TURNSTILE_SECRET_KEY=secretref:turnstile-secret-key")
[[ -n "${FUTBOARD_DATABASE_URL:-}" ]] && \
  BACKEND_ENV_VARS+=("FUTBOARD_DATABASE_URL=secretref:futboard-database-url")

# There is deliberately no AZURE_OPENAI_* or AZURE_SEARCH_* block. Both resources
# were deleted from the subscription; generation runs against the OpenAI API
# directly and retrieval against the index baked into the image.

echo "Actualizando imagen backend en Azure Container Apps..."
az containerapp update \
  --name "$AZ_BACKEND_APP" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --image "$BACKEND_IMAGE" \
  --min-replicas "$BACKEND_MIN_REPLICAS" \
  --max-replicas "$BACKEND_MAX_REPLICAS" \
  --set-env-vars "${BACKEND_ENV_VARS[@]}"

echo
# An empty string is not a leaked credential. JMESPath treats '' as != null, so
# the check flagged TURNSTILE_SECRET_KEY="" — left over from a deploy made while
# captcha was still configured — and aborted before the frontend was published.
echo "Comprobando que ninguna credencial quedó en texto plano..."
LEAKED=$(az containerapp show --name "$AZ_BACKEND_APP" --resource-group "$AZ_RESOURCE_GROUP" \
  --query "properties.template.containers[0].env[?value!=null && value!='' && (contains(name,'KEY') || contains(name,'SECRET') || contains(name,'DATABASE_URL'))].name" \
  --output tsv)
if [[ -n "$LEAKED" ]]; then
  echo "ERROR: estas variables tienen valor en texto plano en lugar de secretref:"
  echo "$LEAKED"
  exit 1
fi
echo "OK: todas las credenciales usan secretref."

echo "Eliminando referencia antigua a ACR si existe..."
az containerapp registry remove \
  --name "$AZ_BACKEND_APP" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --server acrdomingorag.azurecr.io || true

echo "Creando Azure Static Web App si no existe..."
if ! az staticwebapp show --name "$AZ_STATIC_WEB_APP" --resource-group "$AZ_RESOURCE_GROUP" >/dev/null 2>&1; then
  az staticwebapp create \
    --name "$AZ_STATIC_WEB_APP" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --location "westeurope" \
    --sku Free
  echo "Static Web App creada."
fi

echo "Obteniendo token de despliegue de Static Web App..."
SWA_TOKEN=$(az staticwebapp secrets list \
  --name "$AZ_STATIC_WEB_APP" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --query "properties.apiKey" -o tsv)

echo "Desplegando frontend en Azure Static Web Apps..."
npx --yes @azure/static-web-apps-cli deploy \
  "$ROOT_DIR/frontend/dist" \
  --deployment-token "$SWA_TOKEN" \
  --env production

echo "Configurando dominio personalizado en Static Web App..."
az staticwebapp hostname set \
  --name "$AZ_STATIC_WEB_APP" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --hostname "$WEB_SUBDOMAIN" || echo "AVISO: el dominio $WEB_SUBDOMAIN ya está configurado o requiere validación DNS manual."

echo "✓ Redeploy completado"
echo "  Backend image: $BACKEND_IMAGE"
echo "  Frontend URL:  https://$WEB_SUBDOMAIN (Azure Static Web Apps)"
