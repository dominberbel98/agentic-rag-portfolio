from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Agentic RAG API"
    app_env: str = "dev"
    app_port: int = 8000

    cors_origins: str = "*"

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-luna"

    # Google Generative AI for embeddings. gemini-embedding-2's space is NOT
    # compatible with gemini-embedding-001 — changing this requires a full
    # reindex with scripts/index_documents.py.
    google_api_key: str | None = None
    embedding_model: str = "gemini-embedding-2"

    # Retrieval and agent loop. top_k is a real limit now: it used to default to
    # 35 over a 25-document corpus, so every query returned the whole thing.
    retrieval_top_k: int = 6
    agent_max_iterations: int = 4
    agent_max_tool_calls: int = 6
    agent_max_documents: int = 8

    # Index locations. The primary path is tried first and the fallback second,
    # so a bad reindex cannot take the service down.
    embeddings_cache_path: str = "embeddings_cache.json"
    embeddings_cache_fallback: str = "embeddings_cache.previous.json"
    vocabulary_path: str = "data/kb/vocabulary.json"

    # Product guardrails
    contact_emails: str = ""
    professional_linkedin: str = ""
    admin_read_key: str = ""
    show_citations: bool = False
    max_requests_per_minute_per_ip: int = 20
    max_tokens_per_day: int = 50000

    # Captcha (Cloudflare Turnstile)
    turnstile_secret_key: str | None = None

    # extra="ignore" on purpose. The container's environment is managed
    # separately from this code (Container Apps env vars and secrets), so a
    # variable that outlives the field that read it must not crash startup.
    # Removing the AZURE_OPENAI_* / AZURE_SEARCH_* fields made exactly that
    # happen: the deployed app still carries those variables.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
