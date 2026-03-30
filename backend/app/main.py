import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.chat import router as chat_router
from app.config import settings
from app.services.rag_service import AgenticRAGService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load embeddings cache at application startup."""
    logger.info("Loading embeddings cache on startup...")
    AgenticRAGService.initialize_cache("embeddings_cache.json")
    logger.info("Startup complete, cache loaded")
    yield
    logger.info("Application shutdown")


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
