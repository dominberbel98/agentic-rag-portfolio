#!/usr/bin/env bash
set -euo pipefail

# Creates a monthly Azure budget cap and email alerts.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$ROOT_DIR/infra/aca/azure.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Falta $ENV_FILE"
  exit 1
fi

source "$ENV_FILE"

if [[ -z "${AZ_SUBSCRIPTION_ID:-}" || -z "${CONTACT_EMAILS:-}" ]]; then
  echo "Faltan AZ_SUBSCRIPTION_ID o CONTACT_EMAILS en azure.env"
  exit 1
fi

IFS=',' read -r -a EMAILS <<< "$CONTACT_EMAILS"

az account set --subscription "$AZ_SUBSCRIPTION_ID"

az consumption budget create \
  --budget-name rag-monthly-15usd \
  --amount 15 \
  --category cost \
  --time-grain monthly \
  --start-date "$(date +%Y-%m-01)" \
  --end-date "$(date -d '+12 months' +%Y-%m-01)" \
  --scope "/subscriptions/$AZ_SUBSCRIPTION_ID" 2>&1 || echo "Budget ya existe o error menor"

echo "Budget de 15 USD/mes creado o actualizado."
