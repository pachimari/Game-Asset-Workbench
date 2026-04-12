from __future__ import annotations

from .gemini_native import GeminiNativeProvider
from .openai_compatible import OpenAICompatibleProvider, ProviderRequestError
from .async_image import AsyncImageProvider
from ..config import (
    ASYNC_IMAGE_SUPPLEMENTAL_MODELS,
    STEP_BRIEF_GENERATION,
    STEP_IMAGE_GENERATION,
    STEP_IMAGE_PROMPT,
)


PROVIDER_LABELS = {
    "gemini": "Gemini",
    "deepseek": "DeepSeek",
    "mock": "本地 Mock",
}

PROVIDER_ORDER = {
    "gemini": 0,
    "deepseek": 1,
    "mock": 9,
}

MODEL_COMPATIBILITY_ORDER = {
    "verified": 0,
    "single_only": 1,
    "experimental": 2,
    "unknown": 3,
    "unsupported": 4,
}

KNOWN_GEMINI_IMAGE_COMPATIBILITY = {
    "models/gemini-2.5-flash-image": "single_only",
    "models/gemini-3-pro-image-preview": "experimental",
    "models/gemini-3.1-flash-image-preview": "verified",
    "models/imagen-4.0-generate-001": "verified",
    "models/imagen-4.0-ultra-generate-001": "verified",
    "models/imagen-4.0-fast-generate-001": "verified",
}


GEMINI_PROVIDER = OpenAICompatibleProvider(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    label="Gemini",
)
GEMINI_NATIVE_PROVIDER = GeminiNativeProvider()

DEEPSEEK_PROVIDER = OpenAICompatibleProvider(
    base_url="https://api.deepseek.com",
    label="DeepSeek",
)


def get_provider(provider_id: str, provider_config: dict | None = None) -> OpenAICompatibleProvider:
    if provider_id == "gemini":
        return GEMINI_PROVIDER
    if provider_id == "deepseek":
        return DEEPSEEK_PROVIDER
    if provider_config and provider_config.get("provider_type") == "openai_compatible":
        return OpenAICompatibleProvider(
            base_url=provider_config.get("base_url", "").rstrip("/"),
            label=provider_config.get("label", provider_id),
        )
    raise ValueError(f"Unsupported provider: {provider_id}")


def get_native_image_provider(provider_id: str, provider_config: dict | None = None):
    if provider_id == "gemini":
        return GEMINI_NATIVE_PROVIDER
    if provider_config and provider_config.get("provider_type") == "gemini_native":
        return GeminiNativeProvider(
            base_url=provider_config.get("base_url", "https://generativelanguage.googleapis.com"),
            label=provider_config.get("label", provider_id),
        )
    raise ValueError(f"Unsupported native image provider: {provider_id}")


def get_async_image_provider(provider_id: str, provider_config: dict | None = None):
    if provider_config and provider_config.get("provider_type") == "async_image":
        return AsyncImageProvider(
            label=provider_config.get("label", provider_id),
            base_url=provider_config.get("base_url", ""),
        )
    raise ValueError(f"Unsupported async image provider: {provider_id}")


def infer_stages(provider_id: str, model_id: str) -> list[str]:
    lower = model_id.lower()
    if provider_id == "gemini":
        if any(token in lower for token in ["embedding", "veo", "aqa", "tts"]):
            return []
        if "image" in lower or "imagen" in lower:
            return [STEP_IMAGE_GENERATION]
        return [STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT]
    if provider_id == "deepseek":
        if "image" in lower or "embedding" in lower:
            return []
        return [STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT]
    return []


def display_label_for_model(provider_id: str, model_id: str) -> str:
    label = model_id.replace("models/", "")
    if provider_id == "gemini":
        label = label.replace("gemini-", "")
    if provider_id == "deepseek":
        label = label.replace("deepseek-", "")
    return label


def compatibility_for_model(provider_id: str, model_id: str) -> str:
    if provider_id == "gemini" and model_id in KNOWN_GEMINI_IMAGE_COMPATIBILITY:
        return KNOWN_GEMINI_IMAGE_COMPATIBILITY[model_id]
    return "unknown"


def _is_async_image_model(row: dict) -> bool:
    model_id = str(row.get("id", "")).lower()
    if "supported_endpoint_types" in row:
        supported_endpoint_types = [str(value).lower() for value in row.get("supported_endpoint_types", [])]
        if not supported_endpoint_types:
            return False
        return any("image" in endpoint for endpoint in supported_endpoint_types)
    return any(
        token in model_id
        for token in (
            "image",
            "imagen",
            "banana",
            "flux",
            "midjourney",
            "mj",
            "seedream",
            "recraft",
            "ideogram",
            "gpt-image",
        )
    )


def _supplement_async_image_models(provider_config: dict | None, discovered_ids: set[str]) -> list[dict]:
    supplemental_models: list[dict] = []
    configured_models = provider_config.get("supplemental_models") if provider_config else None
    model_ids: tuple[str, ...] | list[str]
    if isinstance(configured_models, list):
        model_ids = [str(model_id).strip() for model_id in configured_models if str(model_id).strip()]
    elif isinstance(configured_models, str) and configured_models.strip():
        model_ids = [model_id.strip() for model_id in configured_models.split(",") if model_id.strip()]
    else:
        model_ids = ASYNC_IMAGE_SUPPLEMENTAL_MODELS
    for model_id in model_ids:
        if model_id in discovered_ids:
            continue
        supplemental_models.append(
            {
                "id": model_id,
                "label": model_id,
                "stages": [STEP_IMAGE_GENERATION],
                "compatibility": "unknown",
            }
        )
    return supplemental_models


def sync_provider_models(provider_id: str, api_key: str, provider_config: dict | None = None) -> list[dict]:
    if provider_id == "mock":
        return []
    if provider_config and provider_config.get("provider_type") == "async_image":
        async_provider = get_async_image_provider(provider_id, provider_config)
        models = []
        for row in async_provider.list_models(api_key=api_key):
            model_id = row.get("id")
            if not model_id or not _is_async_image_model(row):
                continue
            models.append(
                {
                    "id": model_id,
                    "label": row.get("display_name") or display_label_for_model(provider_id, model_id),
                    "stages": [STEP_IMAGE_GENERATION],
                    "compatibility": compatibility_for_model(provider_id, model_id),
                }
            )
        discovered_ids = {model["id"] for model in models}
        models.extend(_supplement_async_image_models(provider_config, discovered_ids))
        models.sort(
            key=lambda model: (
                MODEL_COMPATIBILITY_ORDER.get(model.get("compatibility", "unknown"), 99),
                model["label"],
            )
        )
        return models
    provider_type = (provider_config or {}).get("provider_type")
    if provider_id == "gemini" or provider_type == "gemini_native":
        provider = get_native_image_provider(provider_id, provider_config)
    else:
        provider = get_provider(provider_id, provider_config)
    models = []
    for row in provider.list_models(api_key=api_key):
        model_id = row.get("id")
        if not model_id:
            continue
        if provider_id not in PROVIDER_LABELS and provider_type == "openai_compatible":
            stages = infer_stages("deepseek", model_id)
        elif provider_id not in PROVIDER_LABELS and provider_type == "gemini_native":
            stages = infer_stages("gemini", model_id)
        else:
            stages = infer_stages(provider_id, model_id)
        if not stages:
            continue
        models.append(
            {
                "id": model_id,
                "label": row.get("display_name")
                or display_label_for_model("gemini" if provider_type == "gemini_native" else provider_id, model_id),
                "stages": stages,
                "compatibility": compatibility_for_model(
                    "gemini" if provider_type == "gemini_native" else provider_id,
                    model_id,
                ),
            }
        )
    models.sort(
        key=lambda model: (
            MODEL_COMPATIBILITY_ORDER.get(model.get("compatibility", "unknown"), 99),
            model["label"],
        )
    )
    return models


__all__ = [
    "ProviderRequestError",
    "PROVIDER_LABELS",
    "PROVIDER_ORDER",
    "display_label_for_model",
    "compatibility_for_model",
    "get_async_image_provider",
    "get_provider",
    "get_native_image_provider",
    "infer_stages",
    "sync_provider_models",
]
