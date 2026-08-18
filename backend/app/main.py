import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.chat import router as chat_router
from app.api.futboard import router as futboard_router
from app.config import settings
from app.services.rag_service import AgenticRAGService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

_raw_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
# Reject wildcard CORS in production to avoid unauthenticated cross-origin access
if "*" in _raw_origins and settings.app_env == "production":
    raise RuntimeError("Wildcard CORS origin is not allowed in production. Set CORS_ORIGINS to explicit domains.")
origins = _raw_origins if _raw_origins and "*" not in _raw_origins else ["*"]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the retrieval index and grounding vocabulary at startup."""
    logger.info("Loading retrieval index on startup...")
    AgenticRAGService.initialize_cache()
    logger.info("Startup complete")
    yield
    logger.info("Application shutdown")


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["POST", "GET", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(futboard_router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    # Do not expose environment name or internal details
    return {"status": "ok"}
