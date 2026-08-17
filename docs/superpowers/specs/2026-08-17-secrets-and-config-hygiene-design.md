# Block 0 — Secrets and config hygiene

**Date:** 2026-08-17
**Depends on:** nothing
**Status:** partially executed (secrets migration done 2026-08-17)

## Problem

Every credential on `rag-backend` was stored as a **plaintext environment
variable** rather than a Container Apps secret. The `secrets` collection held
only the two GHCR registry logins. Plaintext env vars are readable by anyone
with Reader on the subscription, are rendered by `az containerapp show`, and are
embedded in ARM/Bicep exports.

Five values were affected: `OPENAI_API_KEY`, `GOOGLE_API_KEY`,
`ADMIN_READ_KEY`, `AZURE_OPENAI_API_KEY`, `AZURE_SEARCH_API_KEY`.

Liveness was verified before acting: `OPENAI_API_KEY` and `GOOGLE_API_KEY` both
returned HTTP 200 against their provider APIs. `ADMIN_READ_KEY` guards the
analytics endpoints. The two Azure keys point at resources that no longer exist
in the subscription.

## Decision on rotation

Rotation was recommended and **declined by the owner**: the keys are being moved
into secrets and kept as-is. This is recorded because it changes the residual
risk — the secrets migration prevents future casual reads, but the values were
already disclosed (they were printed to a terminal during investigation) and
therefore remain compromised until rotated. Migration and rotation are
independent; rotating later requires only `az containerapp secret set` with new
values, with no revision or code change.

## Completed

All five values now resolve through `secretRef`; no plaintext credential remains
in the container template. Secret names follow the existing kebab-case
convention: `openai-api-key`, `google-api-key`, `admin-read-key`,
`azure-openai-api-key`, `azure-search-api-key`. This produced revision
`rag-backend--0000050`.

## Remaining

**Delete the dead configuration.** These six env vars point at resources that
were removed from the subscription:

- `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`,
  `AZURE_OPENAI_CHAT_DEPLOYMENT`
- `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_API_KEY`, `AZURE_SEARCH_INDEX_NAME`

Because `OPENAI_API_KEY` is set, `_build_llm_client` never reaches the
`AzureOpenAI` branch, so removing them is behaviour-preserving. Removal must be
paired with the code change in Block B that drops the unreachable branch —
otherwise the config and the code keep disagreeing about the architecture.

**Align the tracked examples.** `backend/.env.example` and
`infra/aca/azure.env.example` advertise `AZURE_SEARCH_*` and `OPENAI_MODEL=gpt-4o-mini`;
neither matches production. They should describe the real shape after the
cleanup.

**Document the secret convention** in `DEPLOYMENT.md` so future deploys do not
reintroduce plaintext values. `scripts/deploy_azure.sh` must be checked for
`--set-env-vars` calls that would overwrite a `secretRef` with a literal.

## Verification

- `az containerapp show ... --query "...env[].{name,value,secretRef}"` shows no
  plaintext value for any credential.
- `GET https://api.domingoberbel.com/health` returns 200.
- A live chat request succeeds — this is the meaningful test, because a broken
  `secretRef` surfaces as an empty API key and a failed completion rather than a
  failed deploy.
- The admin analytics endpoint still authenticates with `ADMIN_READ_KEY`.
