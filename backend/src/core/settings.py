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
    
    # CORS
    allowed_origins: Union[str, List[str]] = "http://localhost:5173,http://localhost:3000"
    
    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_price_id: str = ""
    stripe_webhook_secret: str = ""
    
    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    
    # File Upload
    max_file_size: int = 10485760  # 10MB
    upload_dir: str = "uploads"
    
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
        return "http://localhost:5173,http://localhost:3000"
    
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


# Global settings instance - lazy loading to avoid initialization issues
_settings = None

def get_settings():
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

# Compatibility alias
settings = get_settings()