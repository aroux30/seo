import json
import time
import re
from datetime import datetime, timezone, timedelta
from uuid import UUID
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_providers import AiProviderKey
from app.core.encryption import decrypt_value
from app.core.exceptions import AppException
from app.config import get_settings

settings = get_settings()

COOLDOWN_MINUTES = 10


def _clean_json_markdown(text: str) -> str:
    """Strip markdown code block fences if LLM wrapped json in ```json ... ```."""
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"```\s*$", "", raw).strip()
    return raw


async def _call_gemini_direct(
    api_key: str,
    model_name: str,
    user_prompt: str,
    system_prompt: str = "",
    json_mode: bool = False,
    temperature: float = 0.7,
    timeout_sec: float = 180.0,
) -> tuple[str, int, int]:
    """Call Google Gemini REST API v1beta directly."""
    # Ensure standard model format
    clean_model = model_name.strip()
    if not clean_model.startswith("gemini-"):
        clean_model = f"gemini-{clean_model}" if clean_model else "gemini-3.6-flash"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={api_key}"

    generation_config: dict = {
        "temperature": temperature,
        "maxOutputTokens": 8192,
    }
    if json_mode:
        generation_config["responseMimeType"] = "application/json"

    contents = [
        {
            "role": "user",
            "parts": [{"text": user_prompt}],
        }
    ]

    payload: dict = {
        "contents": contents,
        "generationConfig": generation_config,
    }
    if system_prompt:
        payload["systemInstruction"] = {
            "parts": [{"text": system_prompt}]
        }

    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        res = await client.post(url, json=payload)
        
        if res.status_code != 200:
            err_text = res.text
            is_rate_limit = (
                res.status_code == 429
                or "RESOURCE_EXHAUSTED" in err_text
                or "quota" in err_text.lower()
            )
            raise AiProviderCallError(
                status_code=res.status_code,
                detail=f"Gemini API Error ({res.status_code}): {err_text[:300]}",
                is_rate_limit=is_rate_limit,
            )

        data = res.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise AiProviderCallError(
                status_code=502,
                detail="Gemini response contained no candidates",
                is_rate_limit=False,
            )

        parts = candidates[0].get("content", {}).get("parts") or []
        text_content = parts[0].get("text", "") if parts else ""
        if json_mode:
            text_content = _clean_json_markdown(text_content)

        usage = data.get("usageMetadata") or {}
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)

        return text_content, prompt_tokens, completion_tokens


async def _call_openai_compatible(
    base_url: str,
    api_key: str,
    model_name: str,
    user_prompt: str,
    system_prompt: str = "",
    json_mode: bool = False,
    temperature: float = 0.7,
    timeout_sec: float = 180.0,
    extra_headers: dict | None = None,
) -> tuple[str, int, int]:
    """Call OpenAI / DeepSeek / OpenRouter chat completions endpoint."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **(extra_headers or {}),
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    payload: dict = {
        "model": model_name or "gpt-4o-mini",
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        res = await client.post(url, headers=headers, json=payload)
        
        if res.status_code != 200:
            err_text = res.text
            is_rate_limit = (
                res.status_code == 429
                or "insufficient_quota" in err_text
                or "rate_limit" in err_text.lower()
            )
            raise AiProviderCallError(
                status_code=res.status_code,
                detail=f"OpenAI/Compatible API Error ({res.status_code}): {err_text[:300]}",
                is_rate_limit=is_rate_limit,
            )

        data = res.json()
        choices = data.get("choices") or []
        if not choices:
            raise AiProviderCallError(
                status_code=502,
                detail="OpenAI response contained no choices",
                is_rate_limit=False,
            )

        text_content = choices[0].get("message", {}).get("content", "")
        if json_mode:
            text_content = _clean_json_markdown(text_content)

        usage = data.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        return text_content, prompt_tokens, completion_tokens


async def _call_claude_direct(
    api_key: str,
    model_name: str,
    user_prompt: str,
    system_prompt: str = "",
    json_mode: bool = False,
    temperature: float = 0.7,
    timeout_sec: float = 180.0,
) -> tuple[str, int, int]:
    """Call Anthropic Claude Messages API."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "model": model_name or "claude-3-5-sonnet-20241022",
        "max_tokens": 8192,
        "temperature": temperature,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if system_prompt:
        payload["system"] = system_prompt

    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        res = await client.post(url, headers=headers, json=payload)
        
        if res.status_code != 200:
            err_text = res.text
            is_rate_limit = res.status_code == 429 or "rate_limit" in err_text.lower()
            raise AiProviderCallError(
                status_code=res.status_code,
                detail=f"Anthropic Claude API Error ({res.status_code}): {err_text[:300]}",
                is_rate_limit=is_rate_limit,
            )

        data = res.json()
        contents = data.get("content") or []
        text_content = contents[0].get("text", "") if contents else ""
        if json_mode:
            text_content = _clean_json_markdown(text_content)

        usage = data.get("usage") or {}
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)

        return text_content, prompt_tokens, completion_tokens


class AiProviderCallError(Exception):
    def __init__(self, status_code: int, detail: str, is_rate_limit: bool = False):
        self.status_code = status_code
        self.detail = detail
        self.is_rate_limit = is_rate_limit
        super().__init__(detail)


async def test_single_ai_key(
    provider_name: str,
    raw_api_key: str,
    model_name: str,
) -> dict:
    """Perform a fast live ping to verify an API key and measure latency."""
    start_t = time.time()
    test_user_prompt = "پاسخ بسیار کوتاه یک کلمه‌ای بده: OK"
    test_system_prompt = "تو یک دستیار تست اتصال API هستی."

    provider = provider_name.lower().strip()
    clean_model = model_name.strip()

    try:
        if provider == "gemini":
            text, p_tok, c_tok = await _call_gemini_direct(
                api_key=raw_api_key,
                model_name=clean_model or "gemini-3.6-flash",
                user_prompt=test_user_prompt,
                system_prompt=test_system_prompt,
                timeout_sec=60.0,
            )
        elif provider == "openai":
            text, p_tok, c_tok = await _call_openai_compatible(
                base_url="https://api.openai.com/v1",
                api_key=raw_api_key,
                model_name=clean_model or "gpt-4o-mini",
                user_prompt=test_user_prompt,
                system_prompt=test_system_prompt,
                timeout_sec=40.0,
            )
        elif provider == "deepseek":
            text, p_tok, c_tok = await _call_openai_compatible(
                base_url="https://api.deepseek.com",
                api_key=raw_api_key,
                model_name=clean_model or "deepseek-chat",
                user_prompt=test_user_prompt,
                system_prompt=test_system_prompt,
                timeout_sec=20.0,
            )
        elif provider == "openrouter":
            text, p_tok, c_tok = await _call_openai_compatible(
                base_url="https://openrouter.ai/api/v1",
                api_key=raw_api_key,
                model_name=clean_model or "google/gemini-3.6-flash-001",
                user_prompt=test_user_prompt,
                system_prompt=test_system_prompt,
                timeout_sec=20.0,
                extra_headers={"HTTP-Referer": "https://seo.arouxpingg.com", "X-Title": "AI SEO OS"},
            )
        elif provider == "claude":
            text, p_tok, c_tok = await _call_claude_direct(
                api_key=raw_api_key,
                model_name=clean_model or "claude-3-5-haiku-20241022",
                user_prompt=test_user_prompt,
                system_prompt=test_system_prompt,
                timeout_sec=20.0,
            )
        else:
            raise AppException(status_code=400, detail=f"ارائه‌دهنده '{provider_name}' پشتیبانی نمی‌شود.", error_type="unsupported_provider")

        latency_ms = int((time.time() - start_t) * 1000)
        return {
            "status": "ok",
            "provider": provider,
            "model": clean_model,
            "latency_ms": latency_ms,
            "response_sample": text.strip()[:100],
        }
    except AiProviderCallError as e:
        latency_ms = int((time.time() - start_t) * 1000)
        raise AppException(
            status_code=e.status_code if e.status_code < 500 else 400,
            detail=f"تست اتصال ناموفق بود: {e.detail}",
            error_type="api_key_test_failed",
        )
    except Exception as e:
        latency_ms = int((time.time() - start_t) * 1000)
        raise AppException(
            status_code=400,
            detail=f"خطا در ارتباط با ارائه‌دهنده هوش مصنوعی: {str(e)}",
            error_type="api_key_test_error",
        )


async def call_ai_with_rotation(
    db: AsyncSession,
    org_id: UUID | None,
    user_prompt: str,
    system_prompt: str = "",
    provider_preference: str | None = None,
    model_preference: str | None = None,
    json_mode: bool = False,
    temperature: float = 0.7,
) -> tuple[str, str, int, int]:
    """Execute AI text generation with multi-key pool rotation and instant 429 failover.

    Returns:
        (generated_text, provider_and_model_used, prompt_tokens, completion_tokens)
    """
    now = datetime.now(timezone.utc)
    cooldown_threshold = now - timedelta(minutes=COOLDOWN_MINUTES)

    # 1. Fetch available keys for this organization (and global keys)
    stmt = (
        select(AiProviderKey)
        .where(
            AiProviderKey.is_active == True,
            (AiProviderKey.organization_id == org_id) | (AiProviderKey.organization_id.is_(None)),
        )
        .order_by(AiProviderKey.priority.asc(), AiProviderKey.created_at.asc())
    )
    res = await db.execute(stmt)
    db_keys = list(res.scalars().all())

    # Separate into ready keys and cooldown keys
    ready_candidates: list[AiProviderKey] = []
    cooldown_candidates: list[AiProviderKey] = []

    for k in db_keys:
        if k.last_error_at and k.last_error_at > cooldown_threshold and k.error_count >= 2:
            cooldown_candidates.append(k)
        else:
            ready_candidates.append(k)

    # If provider_preference is requested, sort those first
    if provider_preference:
        pref = provider_preference.lower()
        ready_candidates.sort(key=lambda k: 0 if k.provider_name.lower() == pref else 1)

    candidates = ready_candidates + cooldown_candidates

    errors_encountered: list[str] = []

    # 2. Iterate through candidate keys in DB pool
    for key_row in candidates:
        provider = key_row.provider_name.lower().strip()
        model = model_preference or key_row.model_name
        try:
            raw_key = decrypt_value(key_row.encrypted_api_key)
        except Exception as dec_err:
            errors_encountered.append(f"Key #{key_row.label}: Decryption failed")
            continue

        try:
            if provider == "gemini":
                text, p_tok, c_tok = await _call_gemini_direct(
                    api_key=raw_key,
                    model_name=model,
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    json_mode=json_mode,
                    temperature=temperature,
                )
            elif provider == "openai":
                text, p_tok, c_tok = await _call_openai_compatible(
                    base_url="https://api.openai.com/v1",
                    api_key=raw_key,
                    model_name=model or "gpt-4o-mini",
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    json_mode=json_mode,
                    temperature=temperature,
                )
            elif provider == "deepseek":
                text, p_tok, c_tok = await _call_openai_compatible(
                    base_url="https://api.deepseek.com",
                    api_key=raw_key,
                    model_name=model or "deepseek-chat",
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    json_mode=json_mode,
                    temperature=temperature,
                )
            elif provider == "openrouter":
                text, p_tok, c_tok = await _call_openai_compatible(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=raw_key,
                    model_name=model or "google/gemini-3.6-flash-001",
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    json_mode=json_mode,
                    temperature=temperature,
                    extra_headers={"HTTP-Referer": "https://seo.arouxpingg.com", "X-Title": "AI SEO OS"},
                )
            elif provider == "claude":
                text, p_tok, c_tok = await _call_claude_direct(
                    api_key=raw_key,
                    model_name=model or "claude-3-5-haiku-20241022",
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    json_mode=json_mode,
                    temperature=temperature,
                )
            else:
                continue

            # Success! Update stats
            key_row.usage_count += 1
            key_row.error_count = 0
            key_row.last_used_at = datetime.now(timezone.utc)
            await db.commit()

            return text, f"{provider}:{model}", p_tok, c_tok

        except AiProviderCallError as e:
            # Record error on key
            key_row.error_count += 1
            key_row.last_error_at = datetime.now(timezone.utc)
            await db.commit()
            errors_encountered.append(f"Key '{key_row.label}' ({provider}): {e.detail}")
            # Rotate to next key!
            continue
        except Exception as e:
            key_row.error_count += 1
            key_row.last_error_at = datetime.now(timezone.utc)
            await db.commit()
            errors_encountered.append(f"Key '{key_row.label}' ({provider}): {str(e)}")
            continue

    # 3. Environment variable fallback (if no DB keys or all DB keys failed)
    env_gemini_key = getattr(settings, "GEMINI_API_KEY", None)
    if env_gemini_key:
        try:
            text, p_tok, c_tok = await _call_gemini_direct(
                api_key=env_gemini_key,
                model_name="gemini-3.6-flash",
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                json_mode=json_mode,
                temperature=temperature,
            )
            return text, "gemini:gemini-3.6-flash (env)", p_tok, c_tok
        except Exception as e:
            errors_encountered.append(f"Env GEMINI_API_KEY: {str(e)}")

    env_openai_key = getattr(settings, "OPENAI_API_KEY", None)
    if env_openai_key:
        try:
            text, p_tok, c_tok = await _call_openai_compatible(
                base_url="https://api.openai.com/v1",
                api_key=env_openai_key,
                model_name="gpt-4o-mini",
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                json_mode=json_mode,
                temperature=temperature,
            )
            return text, "openai:gpt-4o-mini (env)", p_tok, c_tok
        except Exception as e:
            errors_encountered.append(f"Env OPENAI_API_KEY: {str(e)}")

    # All keys exhausted
    err_summary = " | ".join(errors_encountered[-3:]) if errors_encountered else "هیچ کلید هوش مصنوعی فعالی ثبت نشده است."
    raise AppException(
        status_code=503,
        detail=f"ارتباط با تمام ارائه‌دهندگان هوش مصنوعی به دلیل محدودیت یا خطا ناموفق بود: {err_summary}",
        error_type="all_ai_providers_exhausted",
    )
