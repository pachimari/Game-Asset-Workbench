from __future__ import annotations

from .gemini_native import GeminiNativeProvider
from .openai_compatible import OpenAICompatibleProvider, ProviderRequestError
from .toapis_async import ToApisAsyncImageProvider
from ..config import STEP_BRIEF_GENERATION, STEP_IMAGE_GENERATION, STEP_IMAGE_PROMPT


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


def get_native_image_provider(provider_id: str):
    if provider_id == "gemini":
        return GEMINI_NATIVE_PROVIDER
    raise ValueError(f"Unsupported native image provider: {provider_id}")


def get_async_image_provider(provider_id: str, provider_config: dict | None = None):
    if provider_config and provider_config.get("provider_type") == "async_image":
        return ToApisAsyncImageProvider(
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


def sync_provider_models(provider_id: str, api_key: str, provider_config: dict | None = None) -> list[dict]:
    if provider_id == "mock":
        return []
    if provider_config and provider_config.get("provider_type") == "async_image":
        return provider_config.get("models", [])
    provider = GEMINI_NATIVE_PROVIDER if provider_id == "gemini" else get_provider(provider_id, provider_config)
    provider_type = (provider_config or {}).get("provider_type")
    models = []
    for row in provider.list_models(api_key=api_key):
        model_id = row.get("id")
        if not model_id:
            continue
        if provider_id not in PROVIDER_LABELS and provider_type == "openai_compatible":
            stages = infer_stages("deepseek", model_id)
        else:
            stages = infer_stages(provider_id, model_id)
        if not stages:
            continue
        models.append(
            {
                "id": model_id,
                "label": row.get("display_name") or display_label_for_model(provider_id, model_id),
                "stages": stages,
                "compatibility": compatibility_for_model(provider_id, model_id),
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
