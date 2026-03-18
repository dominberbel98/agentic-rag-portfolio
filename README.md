# Agentic RAG — Personal Portfolio Chatbot

Full-stack RAG (Retrieval-Augmented Generation) chatbot that answers questions about my professional profile. Built with FastAPI, React, OpenAI and Azure AI Search, deployed on Azure Container Apps.

**Live:** [domingoberbel.com](https://domingoberbel.com)

## Architecture

```
User → Nginx (React SPA) → FastAPI API → OpenAI + Azure AI Search
```

- **Backend:** FastAPI, OpenAI SDK (direct or Azure OpenAI), Azure AI Search for document retrieval
- **Frontend:** React 18 + Vite, served by Nginx with full security headers (CSP, HSTS, X-Frame-Options)
- **Infra:** Azure Container Apps, Azure Container Registry, managed TLS certificates
- **Security:** Rate limiting, token budget, admin key auth, security headers middleware, CORS

## Project Structure

```
backend/          → FastAPI app (RAG logic, guardrails, analytics)
frontend/         → React + Vite chat interface
infra/aca/        → Azure Container Apps config and env templates
scripts/          → Deployment, document indexing, budget setup
docker-compose.yml → Local development stack
```

## Local Development

1. Copy environment templates:

```bash
cp backend/.env.example backend/.env
cp infra/aca/azure.env.example infra/aca/azure.env
# Fill in your real values
```

2. Start the stack:

```bash
docker compose up --build
```

3. Verify:
   - Frontend: http://localhost:3000
   - Backend: http://localhost:8000/health

## Azure Deployment

1. Fill `infra/aca/azure.env` with your Azure and OpenAI credentials.

2. Login and deploy:

```bash
az login
source infra/aca/azure.env
chmod +x scripts/deploy_azure.sh
./scripts/deploy_azure.sh
```

3. Index documents:

```bash
export PYTHONPATH=$PWD
python scripts/index_documents.py
```

4. Configure DNS (CNAME records for your domain → Container Apps FQDNs).

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full step-by-step guide.

## Security

- HTTP security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy) on both frontend and backend
- Rate limiting per IP
- Daily token budget to control LLM costs
- Admin endpoints protected by API key
- No secrets committed to version control — all sensitive values loaded from environment

## Cost Optimization

- `minReplicas=0` on both Container Apps (scale to zero when idle)
- `maxReplicas` capped at 3 (backend) / 2 (frontend)
- Basic SKU ACR
- Trade-off: cold start on first request after inactivity

## Tech Stack

| Layer     | Technology                          |
|-----------|-------------------------------------|
| LLM       | OpenAI API (gpt-4.1-mini)          |
| Retrieval | Azure AI Search                     |
| Backend   | FastAPI, Uvicorn, Pydantic          |
| Frontend  | React 18, Vite, Nginx              |
| Infra     | Azure Container Apps, ACR           |
| CI/CD     | Bash deploy script + Docker         |

## License

MIT
