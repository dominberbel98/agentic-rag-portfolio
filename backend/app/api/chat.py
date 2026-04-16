import logging
from hmac import compare_digest

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.responses import StreamingResponse
import json

logger = logging.getLogger(__name__)

from app.models import ChatRequest, ChatResponse
from app.config import settings
from app.services.analytics_store import AnalyticsStore
from app.services.captcha_service import CaptchaService
from app.services.guards import RequestGuards
from app.services.rag_service import AgenticRAGService

router = APIRouter(tags=["chat"])
rag_service = AgenticRAGService()
analytics_store = AnalyticsStore()
guards = RequestGuards(
    per_minute_limit=settings.max_requests_per_minute_per_ip,
    daily_token_limit=settings.max_tokens_per_day,
)
captcha_service = CaptchaService(secret_key=settings.turnstile_secret_key)


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")

    rate_decision = guards.enforce_rate_limit(client_ip)
    if not rate_decision.allowed:
        raise HTTPException(status_code=429, detail=rate_decision.message)

    if not captcha_service.validate(payload.captcha_token, client_ip):
        raise HTTPException(status_code=400, detail="Captcha invalido")

    estimated_tokens = max(100, len(payload.question) // 3)
    today_usage = analytics_store.get_today_usage()
    budget_decision = guards.enforce_token_budget(today_usage.tokens_used, estimated_tokens)
    if not budget_decision.allowed:
        raise HTTPException(status_code=429, detail=budget_decision.message)

    try:
        history = [{"role": m.role, "content": m.content} for m in payload.history]
        response = rag_service.ask(payload.question, payload.top_k, history=history)
        analytics_store.increment_today_usage(estimated_tokens)
        analytics_store.log_question(
            client_ip=client_ip,
            user_agent=user_agent,
            question=payload.question,
            answer_preview=response.answer,
            out_of_scope=response.needs_contact_form,
        )
        return response
    except Exception as exc:  # pragma: no cover
        logger.error("Unexpected error in /chat: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/chat/stream")
def chat_stream(payload: ChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")

    rate_decision = guards.enforce_rate_limit(client_ip)
    if not rate_decision.allowed:
        raise HTTPException(status_code=429, detail=rate_decision.message)

    if not captcha_service.validate(payload.captcha_token, client_ip):
        raise HTTPException(status_code=400, detail="Captcha invalido")

    estimated_tokens = max(100, len(payload.question) // 3)
    today_usage = analytics_store.get_today_usage()
    budget_decision = guards.enforce_token_budget(today_usage.tokens_used, estimated_tokens)
    if not budget_decision.allowed:
        raise HTTPException(status_code=429, detail=budget_decision.message)

    analytics_store.increment_today_usage(estimated_tokens)

    history = [{"role": m.role, "content": m.content} for m in payload.history]

    def _stream_and_log():
        collected_tokens = []
        out_of_scope = False
        try:
            for chunk in rag_service.ask_stream(payload.question, payload.top_k, history=history):
                yield chunk
                # Parse SSE data lines to capture answer text
                if chunk.startswith("data: "):
                    try:
                        payload_data = json.loads(chunk[6:])
                        if payload_data.get("done"):
                            out_of_scope = payload_data.get("needs_contact_form", False)
                        elif "token" in payload_data:
                            collected_tokens.append(payload_data["token"])
                    except (json.JSONDecodeError, KeyError):
                        pass
        finally:
            # Log with real answer even if client disconnects mid-stream
            full_answer = "".join(collected_tokens).strip()
            analytics_store.log_question(
                client_ip=client_ip,
                user_agent=user_agent,
                question=payload.question,
                answer_preview=full_answer or "(empty)",
                out_of_scope=out_of_scope,
            )

    return StreamingResponse(
        _stream_and_log(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

def _check_admin_key(x_admin_key: str) -> None:
    """Timing-safe admin key check to prevent timing attacks."""
    if not settings.admin_read_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not compare_digest(x_admin_key, settings.admin_read_key):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/admin/questions")
def recent_questions(
    x_admin_key: str = Header(default=""),
) -> dict[str, list[dict[str, str | int]]]:
    _check_admin_key(x_admin_key)
    return {"items": analytics_store.get_recent_questions(limit=200)}


@router.get("/admin/questions-json")
def json_questions(
    x_admin_key: str = Header(default=""),
) -> dict[str, list[dict[str, str | bool]]]:
    _check_admin_key(x_admin_key)
    return {"items": analytics_store.get_json_logs(limit=500)}
