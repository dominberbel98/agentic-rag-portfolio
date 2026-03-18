#!/usr/bin/env bash
# Final deployment checklist for domingoberbel.com RAG

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$ROOT_DIR/infra/aca/azure.env"

echo "=========================================="
echo "Deployment Checklist: domingoberbel.com RAG"
echo "=========================================="
echo ""

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE no encontrado"
  exit 1
fi

source "$ENV_FILE"

echo "✓ Subscription ID: $AZ_SUBSCRIPTION_ID"
echo "✓ Resource Group: $AZ_RESOURCE_GROUP"
echo "✓ Location: $AZ_LOCATION"
echo "✓ Backend App: $AZ_BACKEND_APP"
echo "✓ Frontend App: $AZ_FRONTEND_APP"
echo "✓ Deployment: $AZURE_OPENAI_CHAT_DEPLOYMENT"
echo "✓ Contact emails: $CONTACT_EMAILS"
echo "✓ LinkedIn: $PROFESSIONAL_LINKEDIN"
echo ""
echo "=========================================="
echo "TODO:"
echo "=========================================="
echo ""
echo "1. Deploy infrastructure to Azure:"
echo "   ./scripts/deploy_azure.sh"
echo ""
echo "2. Index your documents (CV, letter):"
echo "   export PYTHONPATH=$ROOT_DIR"
echo "   python scripts/index_documents.py"
echo ""
echo "3. Setup monthly budget cap ($15 USD):"
echo "   ./scripts/setup_budget.sh"
echo ""
echo "4. Configure DNS in Hostinger:"
echo "   - CNAME api -> <backend-fqdn>"
echo "   - CNAME www -> <frontend-fqdn>"
echo "   - Redirect @ -> www"
echo ""
echo "5. Link custom domains in Azure Container Apps:"
echo "   az containerapp hostname add -g $AZ_RESOURCE_GROUP -n $AZ_BACKEND_APP --hostname api.domingoberbel.com"
echo "   az containerapp hostname add -g $AZ_RESOURCE_GROUP -n $AZ_FRONTEND_APP --hostname www.domingoberbel.com"
echo ""
echo "6. Verify HTTPS and DNS:"
echo "   curl https://api.domingoberbel.com/health"
echo "   curl https://www.domingoberbel.com"
echo ""
echo "=========================================="
