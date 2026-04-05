from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # LLM Providers
    GROQ_API_KEY: str = "dummy_for_dev"
    ANTHROPIC_API_KEY: str = "dummy_for_dev"
    GROQ_MODEL: str = "llama-3.1-70b-versatile"
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"
    LLM_TIMEOUT_SECONDS: int = 3

    # Google Cloud (Calendar, Sheets, STT, TTS)
    GOOGLE_SERVICE_ACCOUNT_PATH: str = "config/service_account.json"
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
    GOOGLE_CALENDAR_ID: str = "primary"
    GOOGLE_SHEET_ID: str = ""
    GOOGLE_SHEET_TAB_NAME: str = "Advisor Pre-Bookings"

    # Gmail
    GMAIL_ADDRESS: str = ""
    GMAIL_APP_PASSWORD: str = ""
    GMAIL_SMTP_HOST: str = "smtp.gmail.com"
    GMAIL_SMTP_PORT: int = 587
    ADVISOR_EMAIL: str = "advisor@example.com"
    ADVISOR_NAME: str = "Financial Advisor"

    # Security — Secure URL token signing
    SECURE_URL_SECRET: str = "dev_secret_change_in_production_minimum32chars"
    SECURE_URL_DOMAIN: str = "http://localhost:8501"
    SECURE_URL_TTL_SECONDS: int = 86400

    # Session Management
    SESSION_TTL_SECONDS: int = 1800
    REDIS_URL: str = "redis://localhost:6379/0"

    # ChromaDB / RAG Pipeline
    CHROMA_DB_PATH: str = "data/chroma_db"
    CHROMA_COLLECTION_NAME: str = "advisor_faq"
    RAG_TOP_K: int = 3
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Booking Logic
    MOCK_CALENDAR_PATH: str = "data/mock_calendar.json"
    ADVISOR_ID: str = "ADV-001"
    CALENDAR_SLOT_DURATION_MINUTES: int = 30
    CALENDAR_HOLD_EXPIRY_HOURS: int = 48
    MAX_REPROMPTS: int = 3
    MAX_TURNS_PER_CALL: int = 20

    # STT / TTS
    DEEPGRAM_API_KEY: str = ""
    STT_CONFIDENCE_THRESHOLD: float = 0.7
    STT_SILENCE_TIMEOUT_SECONDS: int = 3
    TTS_VOICE_NAME: str = "en-IN-Neural2-A"
    TTS_CACHE_DIR: str = "data/tts_cache"
    TTS_CACHE_TTL_DAYS: int = 7

    # Logging & Observability
    LOG_LEVEL: str = "INFO"
    VOICE_AUDIT_LOG_PATH: str = "data/logs/voice_audit_log.jsonl"
    MCP_OPS_LOG_PATH: str = "data/logs/mcp_ops_log.jsonl"
    LOG_TO_STDOUT: bool = True

    # Application
    ENVIRONMENT: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    STREAMLIT_PORT: int = 8501
    COMPANY_NAME: str = "YourCompany"
    RUN_INTEGRATION: bool = False


settings = Settings()
