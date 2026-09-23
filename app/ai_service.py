"""
AI Accuracy Layer — SenseNova Integration

SenseNova Endpoint: https://api.hcnsec.cn/v1
Model: sensenova-6.8-flash-lite (fast, accurate, cost-effective)

Features:
  ✓ Fast response times (ideal for real-time applications)
  ✓ High accuracy medical coding
  ✓ Cost-effective usage
  ✓ Automatic fallback to hybrid search on any failure
"""
import json
import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

CHAT_URL = f"{settings.AI_API_BASE_URL}/chat/completions"

# Cache the health check briefly
_health_cache: dict | None = None
_health_cache_at: float = 0.0
HEALTH_CACHE_TTL = 15  # seconds

# Cache AI refine results
_refine_cache: dict[str, dict | None] = {}
_refine_cache_max_size = 256

SYSTEM_PROMPT = """You are a MedDRA coding expert. Your task is to:
1. Interpret the user's free-text symptom/complaint into clinical meaning
2. Select the best MedDRA codes from the provided candidates
3. Suggest additional clinical search terms if needed

Respond ONLY with JSON:
{
  "interpretation": "clinical interpretation of user's phrase",
  "ranked_term_ids": [id1, id2, id3],
  "need_more": false,
  "suggested_terms": [],
  "reason": "why you selected these terms"
}"""


def _headers() -> dict:
    """Return authorization headers for SenseNova API."""
    return {
        "Authorization": f"Bearer {settings.AI_API_KEY}",
        "Content-Type": "application/json",
    }


def _classify_error(status_code: int, body: str) -> str:
    """Classify API error for user-facing message."""
    if status_code in (401, 403):
        return "SenseNova API key invalid or expired"
    if status_code == 429:
        return "SenseNova API rate limit exceeded"
    if status_code == 404:
        return "SenseNova endpoint not found"
    if status_code >= 500:
        return "SenseNova service unavailable"
    
    low = (body or "").lower()
    if "quota" in low or "insufficient" in low:
        return "SenseNova quota exhausted"
    if "invalid" in low and "key" in low:
        return "SenseNova API key invalid"
    
    return f"SenseNova API error (HTTP {status_code})"


def _extract_text(data: dict) -> str:
    """Extract response text from SenseNova response."""
    choices = data.get("choices") or []
    if not choices:
        return ""
    
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    
    if isinstance(content, str) and content.strip():
        return content
    
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text") or part.get("content") or "")
            elif isinstance(part, str):
                parts.append(part)
        joined = "".join(parts).strip()
        if joined:
            return joined
    
    return ""


class SenseNovaAIService:
    """SenseNova AI integration for MedDRA coding accuracy."""

    @staticmethod
    def _candidate_block(candidates: list[dict]) -> str:
        """Format candidates for AI prompt."""
        lines = []
        for c in candidates:
            lines.append(
                f'{c["term_id"]} | LLT: {c["term"]} | PT: {c["pt"]} | SOC: {c.get("soc") or "-"}'
            )
        return "\n".join(lines)

    @classmethod
    async def check_health(cls, force: bool = False) -> dict:
        """Check if SenseNova API is reachable and key is valid."""
        global _health_cache, _health_cache_at

        if not settings.AI_API_KEY:
            return {"configured": False, "live": False, "detail": "AI_API_KEY not set"}

        now = time.monotonic()
        if not force and _health_cache is not None and (now - _health_cache_at) < HEALTH_CACHE_TTL:
            return _health_cache

        result = await cls._check_via_chat_ping()
        _health_cache, _health_cache_at = result, now
        return result

    @classmethod
    async def _check_via_chat_ping(cls) -> dict:
        """Health check via minimal chat completion."""
        body = {
            "model": settings.AI_MODEL,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
            "temperature": 0.0,
        }
        
        timeout = httpx.Timeout(connect=8.0, read=15.0, write=8.0, pool=5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(CHAT_URL, json=body, headers=_headers())
        except Exception as e:
            return {
                "configured": True,
                "live": False,
                "detail": f"SenseNova unreachable — {e}",
            }

        if resp.status_code == 200:
            return {
                "configured": True,
                "live": True,
                "status_code": 200,
                "model": settings.AI_MODEL,
            }

        return {
            "configured": True,
            "live": False,
            "status_code": resp.status_code,
            "detail": _classify_error(resp.status_code, resp.text[:200]),
        }

    @classmethod
    async def refine(cls, query: str, candidates: list[dict]) -> dict | None:
        """Call SenseNova to interpret + re-rank results.
        
        Returns parsed response or None on failure.
        """
        if not settings.AI_API_KEY:
            return None

        # Cache key: query + first 3 candidate IDs
        cache_key = query.lower() + "|" + "|".join(str(c["term_id"]) for c in candidates[:3])
        if cache_key in _refine_cache:
            return _refine_cache[cache_key]

        prompt = (
            f"USER QUERY: {query!r}\n\n"
            f"CANDIDATES:\n{cls._candidate_block(candidates)}\n\n"
            "Respond with JSON only."
        )

        body = {
            "model": settings.AI_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 256,
        }

        # Generous timeouts for SenseNova (can be slower than simple APIs)
        timeout = httpx.Timeout(connect=8.0, read=25.0, write=8.0, pool=5.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(CHAT_URL, json=body, headers=_headers())

            if resp.status_code != 200:
                logger.warning(f"SenseNova HTTP {resp.status_code}: {resp.text[:200]}")
                _refine_cache[cache_key] = None
                return None

            try:
                data = resp.json()
            except json.JSONDecodeError:
                logger.error(f"SenseNova returned non-JSON: {resp.text[:500]}")
                _refine_cache[cache_key] = None
                return None

            text = _extract_text(data).strip()
            
            # Strip markdown fences if present
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:].strip()

            if not text:
                logger.warning(f"SenseNova returned empty content")
                _refine_cache[cache_key] = None
                return None

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as je:
                logger.error(f"SenseNova JSON parse failed: {je}; text: {text[:300]}")
                _refine_cache[cache_key] = None
                return None

            # Normalize and validate response shape
            result = {
                "interpretation": str(parsed.get("interpretation", "")).strip(),
                "ranked_term_ids": [
                    int(x) for x in parsed.get("ranked_term_ids", [])
                    if str(x).lstrip("-").isdigit()
                ],
                "need_more": bool(parsed.get("need_more", False)),
                "suggested_terms": [
                    str(t).strip() for t in parsed.get("suggested_terms", [])
                    if str(t).strip()
                ][:5],
                "reason": str(parsed.get("reason", "")).strip(),
            }

            # Cache the result
            _refine_cache[cache_key] = result
            if len(_refine_cache) > _refine_cache_max_size:
                _refine_cache.pop(next(iter(_refine_cache)))

            logger.info(f"SenseNova: '{query}' → {len(result['ranked_term_ids'])} codes ranked")
            return result

        except httpx.TimeoutException as e:
            logger.error(f"SenseNova timeout: {type(e).__name__} — provider too slow")
            _refine_cache[cache_key] = None
            return None
        except Exception as e:
            logger.error(f"SenseNova refine failed: {type(e).__name__}: {e!r}")
            _refine_cache[cache_key] = None
            return None


async def ai_search(engine, query: str, top_k: int) -> dict:
    """AI-assisted MedDRA coding using SenseNova.
    
    Hybrid search → AI re-rank/interpret → optional expanded search.
    Falls back to plain hybrid search on any AI failure.
    """
    base = engine.search(query, top_k=max(top_k, 15))

    refined = await SenseNovaAIService.refine(query, base[:10]) if base else None
    if not refined:
        return {
            "query": query,
            "count": len(base[:top_k]),
            "results": base[:top_k],
            "ai": {"used": False}
        }

    pool = {c["term_id"]: c for c in base}

    # Expand with AI's suggested terms if needed
    expanded_terms = []
    if refined["need_more"] and refined["suggested_terms"]:
        for term in refined["suggested_terms"]:
            expanded_terms.append(term)
            for c in engine.search(term, top_k=6):
                pool.setdefault(c["term_id"], c)

    # Build final ordering: AI picks first, then rest by confidence
    ordered, seen = [], set()
    for tid in refined["ranked_term_ids"]:
        rec = pool.get(tid) or _record_from_engine(engine, tid)
        if rec and tid not in seen:
            r = dict(rec)
            r["ai_pick"] = True
            ordered.append(r)
            seen.add(tid)

    rest = sorted(
        (c for tid, c in pool.items() if tid not in seen),
        key=lambda c: c["confidence"],
        reverse=True
    )
    ordered.extend(rest)

    # Deduplicate by PT
    final, seen_pt = [], set()
    for r in ordered:
        key = (r.get("pt") or r["term"]).lower()
        if key in seen_pt:
            continue
        seen_pt.add(key)
        final.append(r)
        if len(final) >= top_k:
            break

    return {
        "query": query,
        "count": len(final),
        "results": final,
        "ai": {
            "used": True,
            "interpretation": refined["interpretation"],
            "reason": refined["reason"],
            "expanded_terms": expanded_terms,
        },
    }


def _record_from_engine(engine, tid: int):
    """Construct a result record from engine by term ID."""
    t = engine.by_id.get(tid)
    if not t:
        return None
    return {
        "term": t["llt"],
        "pt": t.get("pt") or t["llt"],
        "soc": t.get("soc"),
        "term_id": t["id"],
        "level": t.get("level", "LLT"),
        "confidence": 0.0,
        "semantic_score": 0.0,
        "lexical_score": 0.0,
        "match_type": "ai",
    }


# Compatibility alias for existing code
AIService = SenseNovaAIService
