# Agentic RAG — Personal Portfolio Chatbot

Full-stack RAG chatbot that answers questions about a professional profile. Built with FastAPI, React, OpenAI-compatible chat models and local cached embeddings, with deployment assets for Azure Container Apps.

**Live:** [domingoberbel.com](https://domingoberbel.com)

## Architecture

```
User → Nginx (React SPA) → FastAPI API → LLM + cached document embeddings
```

- **Backend:** FastAPI, OpenAI SDK (direct or Azure OpenAI), Google embeddings + local hybrid retrieval cache
- **Frontend:** React 18 + Vite, served by Nginx in containers
- **Infra:** Docker Compose locally, Azure Container Apps deployment scripts/templates
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

2. Start the stack with Docker:

```bash
docker compose up --build
```

3. Verify:
   - Frontend: http://localhost:3000
   - Backend: http://localhost:8000/health

4. Optional direct frontend development:

```bash
cd frontend
npm install
npm run dev
```

Vite runs on `http://localhost:5173`, so `CORS_ORIGINS` should include both `http://localhost:3000` and `http://localhost:5173` during mixed local development.

## Azure Deployment

1. Fill `infra/aca/azure.env` with your Azure and OpenAI credentials.

2. Login and prepare the Azure resources/images:

```bash
az login
source infra/aca/azure.env
chmod +x scripts/deploy_azure.sh
./scripts/deploy_azure.sh
```

The script creates the resource group and Container Apps environment, builds/pushes the images, and then prints the remaining manual Container Apps configuration steps.

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

- `minReplicas=0` on both Container Apps if you optimize for cost over cold-start latency
- `maxReplicas` capped at 3 (backend) / 2 (frontend)
- GHCR avoids paying for a dedicated Azure registry
- Trade-off: cold start on first request after inactivity

## Tech Stack

| Layer     | Technology                          |
|-----------|-------------------------------------|
| LLM       | OpenAI API or Azure OpenAI          |
| Retrieval | Local cached embeddings + BM25      |
| Backend   | FastAPI, Uvicorn, Pydantic          |
| Frontend  | React 18, Vite, Nginx               |
| Infra     | Azure Container Apps, GHCR          |
| CI/CD     | Bash deploy script + Docker         |

## License

MIT
