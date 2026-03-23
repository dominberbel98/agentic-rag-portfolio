from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=8000)
    top_k: int = Field(default=10, ge=1, le=10)
    captcha_token: str | None = None
    history: list[HistoryMessage] = Field(default_factory=list, max_items=20)


class Citation(BaseModel):
    source: str
    chunk: str


class ChatResponse(BaseModel):
    answer: str
    used_retrieval: bool
    citations: list[Citation]
    needs_contact_form: bool = False
    contact_emails: list[str] = Field(default_factory=list)
    contact_linkedin: str | None = None
