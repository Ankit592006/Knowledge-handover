"""Open-Source Model Adapter Abstraction (Ollama / Cloud OpenAI-Compatible / Disclosed Extractive Engine)."""

import time
from typing import Any, Callable, Dict, Tuple, Type, TypeVar
import httpx
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()
T = TypeVar("T", bound=BaseModel)


class ModelExecutionMetadata(BaseModel):
    provider_requested: str
    provider_used: str
    model_name: str
    live_llm_invoked: bool
    latency_ms: float
    fallback_reason: str | None = None


def invoke_structured_model(
    system_prompt: str,
    user_prompt: str,
    response_schema: Type[T],
    deterministic_extractor: Callable[[], T],
) -> Tuple[T, ModelExecutionMetadata]:
    """
    Attempt live open-source LLM inference via:
      1. Local Ollama runtime (LLM_PROVIDER="ollama")
      2. Cloud or self-hosted OpenAI-compatible open-source runtime such as Groq, Together, vLLM, or OpenRouter
         (LLM_PROVIDER="openai_compatible", LLM_BASE_URL, LLM_API_KEY, LLM_MODEL_NAME)
    If no LLM server is configured or reachable, execute the evidence-grounded extractive engine and transparently
    record the exact provider in telemetry.
    """
    start_ts = time.perf_counter()
    active_settings = get_settings()
    provider_req = active_settings.LLM_PROVIDER.strip().lower()

    if provider_req in ("ollama", "openai_compatible"):
        try:
            if provider_req == "ollama":
                url = f"{active_settings.LLM_BASE_URL.rstrip('/')}/api/chat"
                payload: Dict[str, Any] = {
                    "model": active_settings.LLM_MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.0},
                }
                with httpx.Client(timeout=min(active_settings.LLM_TIMEOUT_SECONDS, 6.0)) as client:
                    resp = client.post(url, json=payload)
                    resp.raise_for_status()
                    raw_json = resp.json().get("message", {}).get("content", "{}")
                    parsed = response_schema.model_validate_json(raw_json)
                    elapsed = round((time.perf_counter() - start_ts) * 1000, 2)
                    return parsed, ModelExecutionMetadata(
                        provider_requested=provider_req,
                        provider_used="ollama_live",
                        model_name=active_settings.LLM_MODEL_NAME,
                        live_llm_invoked=True,
                        latency_ms=elapsed,
                    )
            else:
                base = active_settings.LLM_BASE_URL.rstrip("/")
                is_local_host = "localhost" in base or "127.0.0.1" in base
                if not active_settings.LLM_API_KEY.strip() and not is_local_host:
                    raise RuntimeError("LLM_API_KEY is not configured for cloud openai_compatible endpoint")
                url = f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"
                headers: Dict[str, str] = {"Content-Type": "application/json"}
                if active_settings.LLM_API_KEY.strip():
                    headers["Authorization"] = f"Bearer {active_settings.LLM_API_KEY.strip()}"
                schema_hint = (
                    f"\n\nYou MUST output a valid JSON object matching this exact JSON Schema:\n"
                    f"{response_schema.model_json_schema()}"
                )
                payload = {
                    "model": active_settings.LLM_MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": system_prompt + schema_hint},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0,
                }
                with httpx.Client(timeout=active_settings.LLM_TIMEOUT_SECONDS) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    raw_json = resp.json()["choices"][0]["message"]["content"].strip()
                    if raw_json.startswith("```"):
                        raw_json = raw_json.strip("`")
                        if raw_json.lower().startswith("json"):
                            raw_json = raw_json[4:].strip()
                    parsed = response_schema.model_validate_json(raw_json)
                    elapsed = round((time.perf_counter() - start_ts) * 1000, 2)
                    return parsed, ModelExecutionMetadata(
                        provider_requested=provider_req,
                        provider_used="openai_compatible_live",
                        model_name=active_settings.LLM_MODEL_NAME,
                        live_llm_invoked=True,
                        latency_ms=elapsed,
                    )
        except Exception as exc:
            fallback_reason = f"LLM runtime ({active_settings.LLM_BASE_URL}) unavailable or schema mismatch: {type(exc).__name__}"
            result = deterministic_extractor()
            elapsed = round((time.perf_counter() - start_ts) * 1000, 2)
            return result, ModelExecutionMetadata(
                provider_requested=provider_req,
                provider_used="deterministic_extractive_fallback",
                model_name="rule-grounded-extractor-v1",
                live_llm_invoked=False,
                latency_ms=elapsed,
                fallback_reason=fallback_reason,
            )

    result = deterministic_extractor()
    elapsed = round((time.perf_counter() - start_ts) * 1000, 2)
    return result, ModelExecutionMetadata(
        provider_requested=provider_req,
        provider_used="deterministic_extractive",
        model_name="rule-grounded-extractor-v1",
        live_llm_invoked=False,
        latency_ms=elapsed,
        fallback_reason=None,
    )
