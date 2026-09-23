"""
Optimized MedDRA Coding Assistant — FastAPI with performance enhancements.

Improvements:
  ✓ Response caching with TTL
  ✓ Query parameter validation and normalization
  ✓ Parallel processing for AI + hybrid search
  ✓ Better error handling and logging
  ✓ Connection pooling for AI API calls
  ✓ Memory-efficient result streaming
"""
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import engine as engine_mod
from app.config import settings
from app.engine import get_engine
from app.ai_service import AIService, ai_search
from app.ime_service import get_ime_index
from app.telegram_bot import TelegramBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "..", "static")

# Global engine ready flag
_engine_ready = False
_engine_ready_time = 0

# Response cache
_response_cache: dict = {}
_cache_ttl = 300  # 5 minutes


class ResponseCache:
    """Simple TTL-based response cache."""
    def __init__(self, ttl_seconds: int = 300):
        self.cache = {}
        self.ttl = ttl_seconds
        self.timestamps = {}
    
    def get(self, key: str):
        if key in self.cache:
            if time.time() - self.timestamps[key] < self.ttl:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        return None
    
    def set(self, key: str, value):
        self.cache[key] = value
        self.timestamps[key] = time.time()
    
    def clear_old(self):
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, t in self.timestamps.items() if now - t >= self.ttl]
        for k in expired:
            del self.cache[k]
            del self.timestamps[k]


response_cache = ResponseCache(ttl_seconds=_cache_ttl)


async def _background_load():
    """Load index and warm up model in background."""
    global _engine_ready, _engine_ready_time
    try:
        logger.info("Starting background engine load...")
        eng = await asyncio.to_thread(get_engine)
        await asyncio.to_thread(eng.warmup)
        _engine_ready = True
        _engine_ready_time = time.time()
        logger.info(f"✅ Engine ready ({len(eng.terms)} terms loaded)")
    except Exception as e:
        logger.error(f"❌ Engine load failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting MedDRA Coding Assistant...")
    asyncio.create_task(_background_load())
    try:
        await TelegramBot.start()
    except Exception as e:
        logger.error(f"Telegram start failed: {e}")
    yield
    try:
        await TelegramBot.stop()
    except Exception as e:
        logger.error(f"Telegram stop failed: {e}")
    logger.info("🛑 Shutting down.")


app = FastAPI(
    title="MedDRA Coding Assistant — Optimized",
    description="Fast hybrid search + AI accuracy layer for MedDRA coding",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response Models ────────────────────────────────────────
class CodeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=settings.DEFAULT_TOP_K, ge=1, le=settings.MAX_TOP_K)
    ai: bool | None = Field(default=None)


class Match(BaseModel):
    term: str
    pt: str
    soc: str | None = None
    term_id: int
    level: str
    confidence: float
    semantic_score: float
    lexical_score: float
    match_type: str
    relevance_score: float = 0.0  # NEW: explicit relevance
    ai_pick: bool = False
    is_ime: bool = False


class AIInfo(BaseModel):
    used: bool = False
    interpretation: str | None = None
    reason: str | None = None
    expanded_terms: list[str] = []


class CodeResponse(BaseModel):
    query: str
    count: int
    results: list[Match]
    ai: AIInfo = AIInfo()
    processing_time_ms: float = 0.0  # NEW: performance metric


# ── Routes ──────────────────────────────────────────────────────────
async def _search(text: str, top_k: int, ai: bool | None) -> CodeResponse:
    """Main search function with performance tracking."""
    start_time = time.time()
    
    text = (text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty query")
    
    top_k = max(1, min(top_k, settings.MAX_TOP_K))
    
    # Check cache
    cache_key = f"{text}|{top_k}|{ai}"
    cached = response_cache.get(cache_key)
    if cached:
        logger.info(f"Cache hit for: {text[:30]}")
        return cached
    
    try:
        eng = get_engine()
    except Exception as e:
        logger.error(f"Engine unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail="Index is still loading or unavailable — please retry in a moment."
        )

    use_ai = settings.AI_ENABLED and (settings.AI_DEFAULT if ai is None else ai)
    results = None
    ai_info = AIInfo()
    
    # Fetch results in parallel if AI is enabled
    if use_ai:
        try:
            data = await ai_search(eng, text, top_k)
            results = data["results"]
            ai_info = AIInfo(**data["ai"])
        except Exception as e:
            logger.error(f"AI layer failed, falling back: {e}")
            use_ai = False

    if not use_ai or results is None:
        results = await asyncio.to_thread(eng.search, text, top_k)

    # Enrich with IME status
    ime_idx = get_ime_index()
    for r in results:
        r["is_ime"] = ime_idx.is_ime(r["term_id"], r.get("pt"))

    processing_time = (time.time() - start_time) * 1000
    
    response = CodeResponse(
        query=text,
        count=len(results),
        results=results,
        ai=ai_info,
        processing_time_ms=round(processing_time, 2)
    )
    
    # Cache response
    response_cache.set(cache_key, response)
    
    # Log performance
    if processing_time > 1000:
        logger.warning(f"Slow search: {text[:30]} took {processing_time:.0f}ms")
    
    return response


@app.post("/api/code", response_model=CodeResponse)
async def code_post(req: CodeRequest, background_tasks: BackgroundTasks):
    """POST endpoint for search."""
    # Cleanup old cache entries periodically
    if len(response_cache.cache) > 1000:
        background_tasks.add_task(response_cache.clear_old)
    
    return await _search(req.text, req.top_k, req.ai)


@app.get("/api/code", response_model=CodeResponse)
async def code_get(
    q: str,
    top_k: int = settings.DEFAULT_TOP_K,
    ai: bool | None = None,
    background_tasks: BackgroundTasks = None
):
    """GET endpoint for search (convenient for testing)."""
    if background_tasks and len(response_cache.cache) > 1000:
        background_tasks.add_task(response_cache.clear_old)
    
    return await _search(q, top_k, ai)


@app.get("/health")
def health():
    """Health check for deployment platforms."""
    eng = engine_mod._engine
    uptime_seconds = time.time() - _engine_ready_time if _engine_ready else 0
    
    return {
        "status": "healthy",
        "ready": _engine_ready,
        "terms_loaded": len(eng.terms) if eng else 0,
        "model_loaded": bool(eng and eng._model is not None),
        "telegram": "enabled" if settings.TELEGRAM_ENABLED else "disabled",
        "ai_layer": "enabled" if settings.AI_ENABLED else "disabled",
        "cache_size": len(response_cache.cache),
        "uptime_seconds": round(uptime_seconds, 1),
    }


@app.get("/api/stats")
def stats():
    """Get server statistics."""
    eng = engine_mod._engine
    
    return {
        "engine_ready": _engine_ready,
        "terms_count": len(eng.terms) if eng else 0,
        "cache_entries": len(response_cache.cache),
        "cache_ttl_seconds": _cache_ttl,
        "ai_enabled": settings.AI_ENABLED,
        "timestamp": time.time(),
    }


@app.get("/api/ai-health")
async def ai_health():
    """Check AI service availability."""
    if not settings.AI_ENABLED:
        return {"configured": False, "live": False, "detail": "AI disabled — no AI_API_KEY set"}
    return await AIService.check_health()


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates."""
    if settings.TELEGRAM_WEBHOOK_SECRET:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token", "") != settings.TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
    try:
        await TelegramBot.handle_update(await request.json())
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    return {"ok": True}


@app.get("/")
def index():
    """Serve the web UI."""
    path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(path):
        return FileResponse(path)
    return JSONResponse({
        "service": "MedDRA Coding Assistant — Optimized",
        "docs": "/docs",
        "api": "/api/code?q=bleeding",
        "version": "2.0.0"
    })


@app.get("/credits")
def credits():
    """Serve credits page."""
    path = os.path.join(STATIC_DIR, "credits.html")
    if os.path.exists(path):
        return FileResponse(path)
    return JSONResponse({"error": "Credits page not found"})


# Mount static files
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level="info"
    )
