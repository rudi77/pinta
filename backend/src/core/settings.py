from pydantic_settings import BaseSettings
from pydantic import field_validator, computed_field
from typing import List, Union
import os


class Settings(BaseSettings):
    """Application configuration settings"""
    
    # Application
    app_name: str = "Maler Kostenvoranschlag API"
    debug: bool = False
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./maler_kostenvoranschlag.db"
    database_pool_max_size: int = 20
    database_pool_overflow: int = 10
    
    # Security
    secret_key: str = "dev-super-secret-jwt-key-must-be-at-least-32-characters-long-change-in-production"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    bcrypt_rounds: int = 12
    
    # OpenAI
    openai_api_key: str = ""
    # Model used for standard text tasks (analysis, questions, quote generation)
    openai_model: str = "gpt-4o-mini"
    # Separate Vision-capable model for multi-modal photo analysis (Premium feature)
    openai_vision_model: str = "gpt-4o"

    # Azure OpenAI (used by pytaskforce via LiteLLM; env vars prefixed AZURE_OPENAI_*).
    # taskforce_setup.bridge_env_for_litellm() maps these to the AZURE_API_*
    # variables LiteLLM expects, so we keep ONE source of truth in .env.
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment: str = "gpt-5.4-mini"

    # ---- pytaskforce Maler-Agent ----------------------------------------
    # Which model alias from pytaskforce' configs/llm_config.yaml to use.
    # "main" → azure/gpt-5.4-mini (default). Other valid aliases:
    # "fast", "powerful", "powerful-1", "claude-sonnet", "claude-haiku", etc.
    # Switch model by setting AGENT_LLM_MODEL_ALIAS in .env, no code change.
    agent_llm_model_alias: str = "main"
    # Maximum react-loop steps per agent.execute() — caps cost runaway.
    agent_max_steps: int = 12

    # Telegram bot (Maler-Agent Messenger Interface)
    telegram_bot_token: str = ""
    # Long-lived shared secret the Telegram bot uses to authenticate its
    # /api/v1/agent/bot/* calls against the Pinta backend. Generate once,
    # set the same value in both backend .env (BOT_SERVICE_TOKEN=...) and
    # the bot's runtime env. Empty = bot adapter cannot reach the backend.
    bot_service_token: str = ""
    # Backend URL the bot adapter calls. For local dev: http://127.0.0.1:8000
    bot_backend_url: str = "http://127.0.0.1:8000"
    # Embedding model for RAG material search
    openai_embedding_model: str = "text-embedding-3-small"
    # Embedding dimension (must match the model; 1536 for text-embedding-3-small)
    openai_embedding_dimension: int = 1536
    # Feature flags
    vision_estimate_enabled: bool = True
    rag_materials_enabled: bool = True
    # When True, AI service errors are raised instead of falling back to static
    # mock responses. Use in tests / iteration scripts so silent failures (e.g.
    # broken prompts, invalid API keys) surface immediately. Production stays
    # False so transient OpenAI hiccups don't break user-facing flows.
    ai_strict_mode: bool = False
    
    # CORS — keep frontend dev ports in sync with frontend/vite.config.js.
    # Override via ALLOWED_ORIGINS env var for prod.
    allowed_origins: Union[str, List[str]] = (
        "http://localhost:5173,http://localhost:5183,http://localhost:3000,"
        "http://127.0.0.1:5173,http://127.0.0.1:5183,http://127.0.0.1:3000"
    )
    
    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_price_id: str = ""
    stripe_webhook_secret: str = ""
    stripe_quote_download_price: float = 4.99  # Price in EUR for single quote download
    
    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""  # Falls leer, wird smtp_user verwendet
    smtp_from_name: str = "Pinta"
    smtp_use_tls: bool = True  # STARTTLS on non-465 ports

    # Application base URL (used for verification links, etc.)
    app_base_url: str = "http://localhost:5173"
    
    # File Upload
    max_file_size: int = 10485760  # 10MB
    upload_dir: str = "uploads"
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""

    # Rate Limiting
    rate_limit_requests: int = 5
    rate_limit_window_minutes: int = 15
    
    @field_validator('allowed_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str) and v:
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        elif isinstance(v, list):
            return v
        return [
            "http://localhost:5173", "http://localhost:5183", "http://localhost:3000",
            "http://127.0.0.1:5173", "http://127.0.0.1:5183", "http://127.0.0.1:3000",
        ]
    
    @computed_field
    @property
    def cors_origins(self) -> List[str]:
        """Get parsed CORS origins as a list"""
        if isinstance(self.allowed_origins, str):
            return [origin.strip() for origin in self.allowed_origins.split(',') if origin.strip()]
        return self.allowed_origins
    
    @field_validator('secret_key')
    @classmethod
    def validate_secret_key(cls, v):
        if not v or len(v) < 32:
            raise ValueError('SECRET_KEY must be at least 32 characters long')
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_ignore_empty = True
        extra = "ignore"


# Global settings instance - lazy loading to avoid initialization issues
_settings = None

def get_settings():
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

# Compatibility alias
settings = get_settings()