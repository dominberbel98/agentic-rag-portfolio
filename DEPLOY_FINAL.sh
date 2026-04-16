#!/usr/bin/env bash
# DEPLOYMENT: domingoberbel.com RAG - Run this script locally

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"

cd "$ROOT_DIR"

echo "=========================================="
echo "PASO 1: Autenticar en Azure (MFA requerida)"
echo "=========================================="
source .venv/bin/activate
source infra/aca/azure.env
# Usa device code flow con tenant específico
az login --use-device-code --tenant "$AZURE_TENANT_ID"
# Abre https://microsoft.com/devicelogin en navegador y entra el código + MFA

echo ""
echo "✓ Autenticación completada"
echo ""

echo "=========================================="
echo "PASO 2: Seleccionar subscription y desplegar"
echo "=========================================="

az account set --subscription "$AZ_SUBSCRIPTION_ID"
echo "✓ Subscription: $AZ_SUBSCRIPTION_ID"

echo ""
echo "✓ Ejecutando despliegue..."
chmod +x scripts/deploy_azure.sh
./scripts/deploy_azure.sh

echo ""
echo "=========================================="
echo "PASO 3: Guardar FQDNs"
echo "=========================================="
BACKEND_FQDN=$(az containerapp show -g "$AZ_RESOURCE_GROUP" -n "$AZ_BACKEND_APP" --query properties.configuration.ingress.fqdn -o tsv)
SWA_DEFAULT_HOSTNAME=$(az staticwebapp show -g "$AZ_RESOURCE_GROUP" -n "$AZ_STATIC_WEB_APP" --query defaultHostname -o tsv)

echo "Backend FQDN: $BACKEND_FQDN"
echo "Frontend SWA:  $SWA_DEFAULT_HOSTNAME"
echo ""
echo "⚠️  GUARDA ESTOS VALORES. Los necesitarás para Hostinger DNS."
echo ""

echo "=========================================="
echo "PASO 4: Ingestar documentos"
echo "=========================================="
export PYTHONPATH="$ROOT_DIR"
"$ROOT_DIR/.venv/bin/python" scripts/index_documents.py
echo "✓ Documentos indexados"

echo ""
echo "=========================================="
echo "PASO 5: Setup de presupuesto (15 USD/mes)"
echo "=========================================="
chmod +x scripts/setup_budget.sh
./scripts/setup_budget.sh
echo "✓ Presupuesto configurado"

echo ""
echo "=========================================="
echo "PASO 6: Configurar Hostinger"
echo "=========================================="
echo ""
echo "Entra a Hostinger y crea estos registros DNS:"
echo ""
echo "1. CNAME: api -> $BACKEND_FQDN"
echo "2. CNAME: www -> $SWA_DEFAULT_HOSTNAME"
echo "3. (if ALIAS available) @ -> www.domingoberbel.com"
echo "   (else) Redirect @ -> www.domingoberbel.com"
echo ""
echo "⏳ Espera 24h para que DNS propague"
echo ""

echo "=========================================="
echo "PASO 7: Vincular dominios en Azure"
echo "=========================================="
echo ""
echo "Ejecuta después que DNS esté configurado:"
echo ""
echo "az containerapp hostname add -g $AZ_RESOURCE_GROUP -n $AZ_BACKEND_APP --hostname api.domingoberbel.com"
echo "az staticwebapp hostname set -g $AZ_RESOURCE_GROUP -n $AZ_STATIC_WEB_APP --hostname www.domingoberbel.com"
echo ""

echo "=========================================="
echo "PASO 8: Verificar HTTPS y SSL"
echo "=========================================="
echo ""
echo "Espera a que Azure emita certificados + DNS propague, luego:"
echo ""
echo "curl https://api.domingoberbel.com/health"
echo "curl https://www.domingoberbel.com"
echo ""
echo "Si ambos devuelven 200, ¡LISTO!"
echo ""

echo "=========================================="
echo "FIN"
echo "=========================================="
echo ""
echo "Para auditoria de preguntas:"
echo "curl -H \"x-admin-key: $ADMIN_READ_KEY\" https://api.domingoberbel.com/api/admin/questions"
echo ""
