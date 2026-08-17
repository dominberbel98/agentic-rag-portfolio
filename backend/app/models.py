from pydantic import BaseModel, Field, field_validator


class HistoryMessage(BaseModel):
    role: str
    content: str = Field(..., max_length=4000)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("user", "assistant"):
            raise ValueError("role must be 'user' or 'assistant'")
        return v


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=8000)
    # Advisory only: the agent chooses how much to retrieve per search now.
    # The old default of 35 exceeded the corpus size, so every query got everything.
    top_k: int = Field(default=6, ge=1, le=50)
    captcha_token: str | None = Field(None, max_length=2048)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)


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
