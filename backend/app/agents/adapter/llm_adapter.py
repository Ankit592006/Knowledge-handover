"""Open-Source Model Adapter Abstraction (Ollama / Local OpenAI-Compatible / Disclosed Extractive Engine)."""

import json
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
    Attempt live open-source LLM inference via Ollama / OpenAI-compatible local runtime with strict JSON schema validation.
    If no local LLM server is reachable on the host (or provider is set to deterministic_extractive), execute the
    evidence-grounded extractive engine and transparently record the exact provider in telemetry.
    """
    start_ts = time.perf_counter()
    provider_req = settings.LLM_PROVIDER.lower()

    if provider_req in ("ollama", "openai_compatible"):
        try:
            if provider_req == "ollama":
                url = f"{settings.LLM_BASE_URL.rstrip('/')}/api/chat"
                payload: Dict[str, Any] = {
                    "model": settings.LLM_MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.0},
                }
                with httpx.Client(timeout=min(settings.LLM_TIMEOUT_SECONDS, 4.0)) as client:
                    resp = client.post(url, json=payload)
                    resp.raise_for_status()
                    raw_json = resp.json().get("message", {}).get("content", "{}")
                    parsed = response_schema.model_validate_json(raw_json)
                    elapsed = round((time.perf_counter() - start_ts) * 1000, 2)
                    return parsed, ModelExecutionMetadata(
                        provider_requested=provider_req,
                        provider_used="ollama_live",
                        model_name=settings.LLM_MODEL_NAME,
                        live_llm_invoked=True,
                        latency_ms=elapsed,
                    )
            else:
                url = f"{settings.LLM_BASE_URL.rstrip('/')}/v1/chat/completions"
                payload = {
                    "model": settings.LLM_MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0,
                }
                with httpx.Client(timeout=min(settings.LLM_TIMEOUT_SECONDS, 4.0)) as client:
                    resp = client.post(url, json=payload)
                    resp.raise_for_status()
                    raw_json = resp.json()["choices"][0]["message"]["content"]
                    parsed = response_schema.model_validate_json(raw_json)
                    elapsed = round((time.perf_counter() - start_ts) * 1000, 2)
                    return parsed, ModelExecutionMetadata(
                        provider_requested=provider_req,
                        provider_used="openai_compatible_live",
                        model_name=settings.LLM_MODEL_NAME,
                        live_llm_invoked=True,
                        latency_ms=elapsed,
                    )
        except Exception as exc:
            fallback_reason = f"Local runtime ({settings.LLM_BASE_URL}) unavailable or schema mismatch: {type(exc).__name__}"
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
