"""
Provider model catalog helpers.

This keeps the frontend model picker current without hardcoding every option
inside the React page.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from backend.config import Settings

logger = logging.getLogger(__name__)

MODEL_CUTOFF = datetime(2025, 1, 1, tzinfo=UTC)
CACHE_TTL_SECONDS = 30 * 60
XAI_MODELS_DOCS_URL = "https://docs.x.ai/docs/models.md"
OPENROUTER_MODELS_API_URL = "https://openrouter.ai/api/v1/models"

ProviderModel = dict[str, Any]
_catalog_cache: dict[str, tuple[float, str, list[ProviderModel]]] = {}


STATIC_PROVIDER_MODELS: dict[str, list[ProviderModel]] = {
    "openai": [
        {
            "id": "gpt-5.2",
            "name": "GPT-5.2",
            "label": "GPT-5.2 (Latest - Recommended)",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": None,
            "description": "Balanced flagship model for complex generation workflows.",
            "source": "static",
            "recommended": True,
        },
        {
            "id": "gpt-5.3-codex",
            "name": "GPT-5.3 Codex",
            "label": "GPT-5.3 Codex (Best for Code)",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": None,
            "description": "Code-focused model for multi-file generation and refactoring.",
            "source": "static",
            "recommended": False,
        },
        {
            "id": "gpt-4o",
            "name": "GPT-4o",
            "label": "GPT-4o",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": None,
            "description": "General-purpose multimodal model.",
            "source": "static",
            "recommended": False,
        },
        {
            "id": "o3",
            "name": "o3",
            "label": "o3 (Best Reasoning)",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": None,
            "description": "High-reasoning model for planning and validation-heavy tasks.",
            "source": "static",
            "recommended": False,
        },
        {
            "id": "o3-mini",
            "name": "o3 Mini",
            "label": "o3 Mini (Faster)",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": None,
            "description": "Lower-latency reasoning model.",
            "source": "static",
            "recommended": False,
        },
    ],
    "gemini": [

        {
            "id": "gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "label": "Gemini 2.5 Flash (Recommended)",
            "pricing_type": "paid",
            "price_summary": "$0.30 / $2.50 per 1M tokens",
            "created_at": None,
            "context_length": 1000000,
            "description": "Fast and efficient model for chat, agents, and production apps. Tested and working.",
            "source": "static",
            "recommended": True,
        },
        {
            "id": "gemini-2.5-flash-lite",
            "name": "Gemini 2.5 Flash Lite",
            "label": "Gemini 2.5 Flash Lite (High Volume)",
            "pricing_type": "paid",
            "price_summary": "$0.10 / $0.40 per 1M tokens",
            "created_at": None,
            "context_length": 1000000,
            "description": "Ultra low-cost model for high-volume AI workloads. Tested and working.",
            "source": "static",
            "recommended": False,
        },
        {
            "id": "gemini-flash-latest",
            "name": "Gemini Flash Latest",
            "label": "Gemini Flash Latest (Auto-Updated)",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": 1000000,
            "description": "Latest release of Gemini Flash - automatically updated. Tested and working.",
            "source": "static",
            "recommended": False,
        },
        {
            "id": "gemini-2.5-pro",
            "name": "Gemini 2.5 Pro",
            "label": "Gemini 2.5 Pro (Most Powerful)",
            "pricing_type": "paid",
            "price_summary": "$1.25 / $10.00 per 1M tokens",
            "created_at": None,
            "context_length": 1000000,
            "description": "High capability model for reasoning, coding and long-context workloads.",
            "source": "static",
            "recommended": False,
        },
        {
            "id": "gemini-pro-latest",
            "name": "Gemini Pro Latest",
            "label": "Gemini Pro Latest (Auto-Updated)",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": 1000000,
            "description": "Latest release of Gemini Pro - automatically updated.",
            "source": "static",
            "recommended": False,
        },
        {
            "id": "gemini-2.0-flash",
            "name": "Gemini 2.0 Flash",
            "label": "Gemini 2.0 Flash",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": 1000000,
            "description": "Previous generation Gemini 2.0 Flash model.",
            "source": "static",
            "recommended": False,
        },
    
    ],
    "deepseek": [
        {
            "id": "deepseek-chat",
            "name": "DeepSeek Chat",
            "label": "DeepSeek V3.2 Chat (Recommended)",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": None,
            "description": "General-purpose DeepSeek chat model.",
            "source": "static",
            "recommended": True,
        },
        {
            "id": "deepseek-reasoner",
            "name": "DeepSeek Reasoner",
            "label": "DeepSeek R1 (Best Reasoning)",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": None,
            "description": "Reasoning-oriented DeepSeek model.",
            "source": "static",
            "recommended": False,
        },
        {
            "id": "deepseek-coder",
            "name": "DeepSeek Coder",
            "label": "DeepSeek Coder V2",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": None,
            "description": "Code-specialized DeepSeek model.",
            "source": "static",
            "recommended": False,
        },
    ],
    "kimi": [
        {
            "id": "kimi-k2.5",
            "name": "Kimi K2.5",
            "label": "Kimi K2.5 (Latest - Recommended)",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": None,
            "description": "Moonshot Kimi flagship model.",
            "source": "static",
            "recommended": True,
        },
        {
            "id": "kimi-k2.5-thinking",
            "name": "Kimi K2.5 Thinking",
            "label": "Kimi K2.5 Thinking (Reasoning)",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": None,
            "description": "Reasoning-oriented Kimi variant.",
            "source": "static",
            "recommended": False,
        },
        {
            "id": "kimi-k2",
            "name": "Kimi K2",
            "label": "Kimi K2",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": None,
            "description": "Previous Kimi generation model.",
            "source": "static",
            "recommended": False,
        },
    ],
}

SUPPORTED_PROVIDERS: list[dict[str, str]] = [
    {"id": "openai", "label": "OpenAI"},
    {"id": "gemini", "label": "Google Gemini"},
    {"id": "deepseek", "label": "DeepSeek"},
    {"id": "kimi", "label": "Kimi (Moonshot)"},
    {"id": "xai", "label": "xAI"},
    {"id": "openrouter", "label": "OpenRouter"},
]


def get_provider_default_models(settings: Settings) -> dict[str, str]:
    """Return the default model per provider."""
    return settings.llm_models


def get_supported_providers(settings: Settings) -> list[dict[str, Any]]:
    """Return provider metadata for the frontend."""
    defaults = get_provider_default_models(settings)
    available = set(settings.available_providers)

    providers: list[dict[str, Any]] = []
    for provider in SUPPORTED_PROVIDERS:
        provider_id = provider["id"]
        providers.append(
            {
                "id": provider_id,
                "label": provider["label"],
                "configured": provider_id in available,
                "default_model": defaults.get(provider_id),
                "catalog_type": "live" if provider_id in {"xai", "openrouter"} else "static",
            }
        )
    return providers


async def get_provider_models(provider: str, settings: Settings) -> tuple[str, list[ProviderModel]]:
    """Return model options for a provider."""
    if provider not in {item["id"] for item in SUPPORTED_PROVIDERS}:
        raise ValueError(f"Unsupported provider '{provider}'")

    if provider in STATIC_PROVIDER_MODELS:
        return "static", STATIC_PROVIDER_MODELS[provider]

    cached = _catalog_cache.get(provider)
    now = time.time()
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1], cached[2]

    if provider == "xai":
        source, models = await _fetch_xai_models()
    elif provider == "openrouter":
        source, models = await _fetch_openrouter_models()
    else:
        source, models = "static", STATIC_PROVIDER_MODELS.get(provider, [])

    _catalog_cache[provider] = (now, source, models)
    return source, models


async def _fetch_xai_models() -> tuple[str, list[ProviderModel]]:
    """Fetch current xAI text models from the official docs markdown."""
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.get(XAI_MODELS_DOCS_URL)
        response.raise_for_status()
        markdown = response.text

    models = _parse_xai_models_markdown(markdown)
    return "xai_docs", models


async def _fetch_openrouter_models() -> tuple[str, list[ProviderModel]]:
    """Fetch current OpenRouter text models from the official models API."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(OPENROUTER_MODELS_API_URL)
        response.raise_for_status()
        payload = response.json()

    models = _normalize_openrouter_models(payload.get("data", []))
    return "openrouter_api", models


def _parse_xai_models_markdown(markdown: str) -> list[ProviderModel]:
    """Parse the xAI models markdown table into dropdown options."""
    models: list[ProviderModel] = []
    seen: set[str] = set()

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line.startswith("| grok-"):
            continue

        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) < 6:
            continue

        model_id, modalities, capabilities, context, rate_limits, pricing = parts[:6]

        if model_id in seen:
            continue
        if "imagine" in model_id or "image" in model_id or "video" in model_id:
            continue
        if not model_id.startswith("grok-"):
            continue
        if "text" not in modalities:
            continue

        seen.add(model_id)
        context_length = _parse_int(context)
        models.append(
            {
                "id": model_id,
                "name": _humanize_xai_model_name(model_id),
                "label": f"{_humanize_xai_model_name(model_id)} (Paid)",
                "pricing_type": "paid",
                "price_summary": pricing or None,
                "created_at": None,
                "context_length": context_length,
                "description": f"Capabilities: {capabilities}. Rate limits: {rate_limits}.",
                "source": XAI_MODELS_DOCS_URL,
                "recommended": len(models) == 0,
            }
        )

    return models


def _normalize_openrouter_models(records: list[dict[str, Any]]) -> list[ProviderModel]:
    """Normalize OpenRouter model payload into frontend-friendly options."""
    models: list[ProviderModel] = []

    for record in records:
        model_id = record.get("id")
        if not model_id:
            continue

        created = _unix_to_datetime(record.get("created"))
        if created and created < MODEL_CUTOFF:
            continue

        architecture = record.get("architecture") or {}
        input_modalities = architecture.get("input_modalities") or []
        output_modalities = architecture.get("output_modalities") or []
        if "text" not in input_modalities or "text" not in output_modalities:
            continue

        pricing = record.get("pricing") or {}
        pricing_type = "free" if _is_openrouter_free(pricing) else "paid"
        display_name = record.get("name") or model_id

        models.append(
            {
                "id": model_id,
                "name": display_name,
                "label": f"{display_name} ({pricing_type.title()})",
                "pricing_type": pricing_type,
                "price_summary": _format_openrouter_pricing(pricing),
                "created_at": created.isoformat() if created else None,
                "context_length": record.get("context_length"),
                "description": record.get("description"),
                "source": OPENROUTER_MODELS_API_URL,
                "recommended": False,
            }
        )

    models.sort(
        key=lambda model: (
            0 if model["pricing_type"] == "free" else 1,
            -(datetime.fromisoformat(model["created_at"]).timestamp()) if model["created_at"] else 0,
            model["name"].lower(),
        )
    )

    if models:
        models[0]["recommended"] = True

    return models


def _humanize_xai_model_name(model_id: str) -> str:
    name = model_id.replace("-", " ")
    name = name.replace("grok", "Grok")
    name = name.replace("beta", "Beta")
    name = name.replace("reasoning", "Reasoning")
    name = name.replace("non reasoning", "Non-Reasoning")
    name = name.replace("multi agent", "Multi-Agent")
    name = name.replace("code fast", "Code Fast")
    return " ".join(part.capitalize() if part.isalpha() else part for part in name.split())


def _is_openrouter_free(pricing: dict[str, Any]) -> bool:
    prompt = pricing.get("prompt")
    completion = pricing.get("completion")
    return _decimal_is_zero(prompt) and _decimal_is_zero(completion)


def _decimal_is_zero(value: Any) -> bool:
    if value is None:
        return False
    try:
        return Decimal(str(value)) == Decimal("0")
    except (InvalidOperation, ValueError):
        return False


def _format_openrouter_pricing(pricing: dict[str, Any]) -> str | None:
    prompt = pricing.get("prompt")
    completion = pricing.get("completion")
    if prompt is None and completion is None:
        return None
    return f"Prompt ${_format_decimal(prompt)} / Completion ${_format_decimal(completion)} per token"


def _format_decimal(value: Any) -> str:
    if value is None:
        return "-"
    text = str(value)
    return text.rstrip("0").rstrip(".") if "." in text else text


def _unix_to_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        logger.debug("Could not parse timestamp %r", value)
        return None


def _parse_int(value: str | None) -> int | None:
    if not value or value == "-":
        return None
    cleaned = value.replace(",", "").strip()
    return int(cleaned) if cleaned.isdigit() else None
