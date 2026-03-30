from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Agentic RAG API"
    app_env: str = "dev"
    app_port: int = 8000

    cors_origins: str = "*"

    openai_api_key: str | None = None
    openai_model: str | None = None

    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str | None = None

    # Google Generative AI for embeddings
    google_api_key: str | None = None

    # Product guardrails
    contact_emails: str = ""
    professional_linkedin: str = ""
    admin_read_key: str = ""
    show_citations: bool = False
    max_requests_per_minute_per_ip: int = 20
    max_tokens_per_day: int = 50000

    # Captcha (Cloudflare Turnstile)
    turnstile_secret_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
