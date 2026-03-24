from __future__ import annotations

from .openai_compatible import OpenAICompatibleProvider, ProviderRequestError
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


GEMINI_PROVIDER = OpenAICompatibleProvider(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    label="Gemini",
)

DEEPSEEK_PROVIDER = OpenAICompatibleProvider(
    base_url="https://api.deepseek.com",
    label="DeepSeek",
)


def get_provider(provider_id: str) -> OpenAICompatibleProvider:
    if provider_id == "gemini":
        return GEMINI_PROVIDER
    if provider_id == "deepseek":
        return DEEPSEEK_PROVIDER
    raise ValueError(f"Unsupported provider: {provider_id}")


def infer_stages(provider_id: str, model_id: str) -> list[str]:
    lower = model_id.lower()
    if provider_id == "gemini":
        if any(token in lower for token in ["embedding", "veo", "aqa", "tts"]):
            return []
        # Keep image-stage filtering narrow to models that are confirmed to
        # work with the OpenAI-compatible image generation endpoint.
        if "image-preview" in lower:
            return []
        if "gemini-2.5-flash-image" in lower or "imagen-" in lower:
            return [STEP_IMAGE_GENERATION]
        if "image" in lower or "imagen" in lower:
            return []
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


def sync_provider_models(provider_id: str, api_key: str) -> list[dict]:
    if provider_id == "mock":
        return []
    provider = get_provider(provider_id)
    models = []
    for row in provider.list_models(api_key=api_key):
        model_id = row.get("id")
        if not model_id:
            continue
        stages = infer_stages(provider_id, model_id)
        if not stages:
            continue
        models.append(
            {
                "id": model_id,
                "label": row.get("display_name") or display_label_for_model(provider_id, model_id),
                "stages": stages,
            }
        )
    models.sort(key=lambda model: model["label"])
    return models


__all__ = [
    "ProviderRequestError",
    "PROVIDER_LABELS",
    "PROVIDER_ORDER",
    "display_label_for_model",
    "get_provider",
    "infer_stages",
    "sync_provider_models",
]
