"""
Optimized Configuration — SenseNova AI Integration
"""
import os
from typing import List

class Settings:
    # ── Server ──────────────────────────────────────────────────────────
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    
    # ── MedDRA Search ────────────────────────────────────────────────────
    DEFAULT_TOP_K: int = 8
    MAX_TOP_K: int = 20
    ENABLE_SEMANTIC: bool = os.getenv("ENABLE_SEMANTIC", "true").lower() == "true"
    
    # ── Caching ─────────────────────────────────────────────────────────
    QUERY_CACHE_SIZE: int = int(os.getenv("QUERY_CACHE_SIZE", 1024))
    QUERY_CACHE_TTL: int = int(os.getenv("QUERY_CACHE_TTL", 3600))
    RESPONSE_CACHE_TTL: int = int(os.getenv("RESPONSE_CACHE_TTL", 300))
    
    # ── CORS ────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    
    # ── SenseNova AI API ────────────────────────────────────────────────
    # NEW: SenseNova (https://api.hcnsec.cn/v1)
    AI_ENABLED: bool = os.getenv("AI_ENABLED", "false").lower() == "true"
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    AI_API_BASE_URL: str = os.getenv(
        "AI_API_BASE_URL", 
        "https://api.hcnsec.cn/v1"  # SenseNova endpoint
    )
    AI_MODEL: str = os.getenv(
        "AI_MODEL", 
        "sensenova-6.8-flash-lite"  # Fast, accurate model
    )
    AI_DEFAULT: bool = os.getenv("AI_DEFAULT", "true").lower() == "true"
    
    # AI Request Timeouts
    AI_CONNECT_TIMEOUT: float = 8.0
    AI_READ_TIMEOUT: float = 20.0
    AI_WRITE_TIMEOUT: float = 8.0
    
    # ── Telegram Bot ────────────────────────────────────────────────────
    TELEGRAM_ENABLED: bool = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_SECRET: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    
    # ── Logging ─────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # ── Feature Flags ───────────────────────────────────────────────────
    ENABLE_QUERY_CACHE: bool = os.getenv("ENABLE_QUERY_CACHE", "true").lower() == "true"
    ENABLE_RESPONSE_CACHE: bool = os.getenv("ENABLE_RESPONSE_CACHE", "true").lower() == "true"
    ENABLE_PREPROCESSING: bool = os.getenv("ENABLE_PREPROCESSING", "true").lower() == "true"


settings = Settings()


# SenseNova API Documentation
"""
SenseNova Endpoint: https://api.hcnsec.cn/v1

Available Models:
- sensenova-6.8-flash-lite : Fast, lightweight, perfect for quick responses
- sensenova-pro : More capable, higher accuracy
- sensenova-turbo : Maximum throughput

Authentication:
  Header: Authorization: Bearer YOUR_API_KEY
  
Example Request:
  POST https://api.hcnsec.cn/v1/chat/completions
  {
    "model": "sensenova-6.8-flash-lite",
    "messages": [{"role": "user", "content": "..."}],
    "temperature": 0.7,
    "max_tokens": 256
  }

Response Format:
  {
    "choices": [{"message": {"content": "..."}}],
    "usage": {"prompt_tokens": ..., "completion_tokens": ...}
  }
"""
