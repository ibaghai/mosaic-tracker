"""Provider-agnostic LLM helper for the v1 job-search assistant.

Reads four env vars to choose any OpenAI-compatible provider:

    LLM_API_BASE   — base URL ending at /v1 (no trailing /chat/completions)
    LLM_API_KEY    — bearer token
    LLM_MODEL      — model id understood by the provider
    LLM_PROVIDER   — optional, just metadata for DB persistence; auto-derived
                     from the API base URL if not set

Provider presets (drop one set into .env.local):

    # Groq (default — fast, free tier, currently rate-limited)
    LLM_API_BASE=https://api.groq.com/openai/v1
    LLM_API_KEY=gsk_...
    LLM_MODEL=llama-3.3-70b-versatile

    # Cerebras (fast like Groq, generous free tier)
    LLM_API_BASE=https://api.cerebras.ai/v1
    LLM_API_KEY=csk-...
    LLM_MODEL=llama-3.3-70b

    # OpenRouter — single key, free `:free` models + paid frontier models
    LLM_API_BASE=https://openrouter.ai/api/v1
    LLM_API_KEY=sk-or-...
    LLM_MODEL=meta-llama/llama-3.3-70b-instruct:free

    # Google Gemini (OpenAI-compatible endpoint)
    LLM_API_BASE=https://generativelanguage.googleapis.com/v1beta/openai
    LLM_API_KEY=AIza...
    LLM_MODEL=gemini-2.5-flash

    # OpenAI
    LLM_API_BASE=https://api.openai.com/v1
    LLM_API_KEY=sk-proj-...
    LLM_MODEL=gpt-4o-mini

    # Together AI
    LLM_API_BASE=https://api.together.xyz/v1
    LLM_API_KEY=...
    LLM_MODEL=meta-llama/Llama-3.3-70B-Instruct-Turbo

Backwards compat: if you only have GROQ_API_KEY set (the original config),
this defaults to Groq. So existing setups keep working without changes.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Optional

USER_AGENT = "Mozilla/5.0 MosaicTracker/1.0"
DEFAULT_TIMEOUT = 120


def _clean_env(raw: Optional[str]) -> str:
    """Strip whitespace plus any non-Latin-1 characters before the value goes
    into an HTTP header. Common copy-paste hazard: pasting a key from a web
    page can pull in U+2028 LINE SEPARATOR or other invisible Unicode that
    Python's http client (Latin-1 by spec) refuses to encode.
    """
    if not raw:
        return ""
    s = raw.strip()
    # Drop anything outside the Latin-1 range. API keys are ASCII by design.
    return s.encode("ascii", errors="ignore").decode("ascii")


def _config(strict: bool = True) -> dict:
    """Resolve LLM config. Raises only when `strict=True` and a call is imminent."""
    api_base = _clean_env(os.getenv("LLM_API_BASE")).rstrip("/")
    api_key = _clean_env(os.getenv("LLM_API_KEY"))
    model = _clean_env(os.getenv("LLM_MODEL") or os.getenv("GROQ_MODEL"))

    # Backwards-compat: original setup only had GROQ_API_KEY + (optional) GROQ_MODEL.
    legacy_groq = _clean_env(os.getenv("GROQ_API_KEY"))
    if not api_base and legacy_groq:
        api_base = "https://api.groq.com/openai/v1"
    if not api_key and legacy_groq:
        api_key = legacy_groq
    if not model:
        model = "llama-3.3-70b-versatile"

    if strict:
        if not api_key:
            raise RuntimeError(
                "LLM not configured. Set LLM_API_KEY (and LLM_API_BASE/LLM_MODEL) "
                "in .env.local. See analysis/llm.py for provider presets."
            )
        if not api_base:
            raise RuntimeError("LLM not configured. Set LLM_API_BASE in .env.local.")

    return {"api_base": api_base, "api_key": api_key, "model": model}


def chat_json(
    messages: list[dict],
    *,
    temperature: float = 0.1,
    timeout: int = DEFAULT_TIMEOUT,
    response_format_json: Optional[bool] = None,
) -> dict:
    """OpenAI-compatible /chat/completions call expecting JSON output.

    Works against any provider with an OpenAI-compatible endpoint: Groq,
    Cerebras, OpenRouter, Together, Fireworks, Gemini-compat, OpenAI, etc.

    response_format_json: if True, sends `response_format: json_object` in the
        request. Some providers (notably Cerebras+Qwen on long prompts) time
        out enforcing this. Set env LLM_JSON_MODE=off to disable globally.
        Default = read from env, falling back to off (the more compatible mode;
        our prompts already instruct strict JSON and we have a regex fallback).

    Returns the parsed JSON body of the assistant's response.
    """
    cfg = _config(strict=True)
    body: dict = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
    }
    use_json_mode = response_format_json
    if use_json_mode is None:
        use_json_mode = (os.getenv("LLM_JSON_MODE", "off").lower() in {"on", "1", "true", "yes"})
    if use_json_mode:
        body["response_format"] = {"type": "json_object"}

    request = urllib.request.Request(
        f"{cfg['api_base']}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"LLM error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc}") from exc

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"LLM returned unexpected payload shape: {payload!r:.200}") from exc

    return _loads_json(content)


def _loads_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def model_name() -> str:
    """Lazy: returns the configured model id, or 'unknown' if unconfigured.

    Used to populate DB metadata; safe to call without an API key set.
    """
    return _config(strict=False)["model"] or "unknown"


def provider_name() -> str:
    """Best-effort provider name derived from `LLM_PROVIDER` or the API base URL.

    Stored in DB columns like `resume_profiles.provider` for analytics. Safe to
    call without a configured key.
    """
    explicit = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if explicit:
        return explicit
    base = _config(strict=False)["api_base"]
    if not base:
        return "unknown"
    matches = [
        ("groq.com", "groq"),
        ("openrouter.ai", "openrouter"),
        ("cerebras.ai", "cerebras"),
        ("together.xyz", "together"),
        ("googleapis.com", "gemini"),
        ("openai.com", "openai"),
        ("fireworks.ai", "fireworks"),
        ("anthropic.com", "anthropic"),
        ("deepinfra.com", "deepinfra"),
    ]
    for needle, name in matches:
        if needle in base:
            return name
    return "openai_compatible"
