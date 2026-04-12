from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from uuid import uuid4

from .config import (
    PROJECT_ROOT,
    STEP_BRIEF_GENERATION,
    STEP_IMAGE_GENERATION,
    STEP_IMAGE_PROMPT,
)
from .providers.registry import (
    MODEL_COMPATIBILITY_ORDER,
    PROVIDER_ORDER,
    compatibility_for_model,
    infer_stages,
)
from .utils import ensure_dir
from .storage import read_json, write_json


SETTINGS_DIR = PROJECT_ROOT / ".local"
APP_SETTINGS_PATH = SETTINGS_DIR / "app_settings.json"
UNSET = object()

DEFAULT_STAGE_SELECTIONS = {
    STEP_BRIEF_GENERATION: {"provider": "mock", "model": "mock-text-v1"},
    STEP_IMAGE_PROMPT: {"provider": "mock", "model": "mock-text-v1"},
    STEP_IMAGE_GENERATION: {"provider": "mock", "model": "mock-image-v1"},
}

DEFAULT_PROMPT_TEMPLATES = {
    "brief_system_prompt": """你是游戏图标前期设计助手。请把用户输入整理成结构化 JSON。
只返回 JSON 对象，不要输出解释文本。
字段必须包含:
- title: string
- name_source: string
- description: string
- keywords: string[]
- icon_subject: string
- visual_focus: string
- project_background: string
- style_requirements: string
""",
    "prompt_system_prompt": """你是游戏图标出图指令助手。请基于设计说明输出结构化 JSON。
只返回 JSON 对象，不要输出解释文本。
字段必须包含:
- prompt: string
- negative_prompt: string
- constraints: object
- batch_context: object
""",
}

DEFAULT_PROVIDER_SETTINGS = {
    "gemini": {
        "provider_type": "gemini_native",
        "label": "Gemini",
        "base_url": "https://generativelanguage.googleapis.com",
        "api_key": "",
        "models": [],
        "last_synced_at": None,
        "last_error": None,
    },
    "deepseek": {
        "provider_type": "openai_compatible",
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "api_key": "",
        "models": [],
        "last_synced_at": None,
        "last_error": None,
    },
    "mock": {
        "provider_type": "mock",
        "label": "本地 Mock",
        "base_url": "",
        "api_key": "",
        "models": [
            {
                "id": "mock-text-v1",
                "label": "本地 Mock 文本",
                "stages": [STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT],
            },
            {
                "id": "mock-image-v1",
                "label": "本地 Mock 出图",
                "stages": [STEP_IMAGE_GENERATION],
            },
        ],
        "last_synced_at": None,
        "last_error": None,
    },
}


def default_global_settings() -> dict:
    return {
        "providers": deepcopy(DEFAULT_PROVIDER_SETTINGS),
        "custom_providers": [],
        "defaults": deepcopy(DEFAULT_STAGE_SELECTIONS),
        "prompt_templates": deepcopy(DEFAULT_PROMPT_TEMPLATES),
    }


def _slugify_provider_name(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip().lower()).strip("-")
    return text or "provider"


def _default_custom_provider(
    *,
    provider_id: str | None = None,
    label: str = "自定义 Provider",
    provider_type: str = "openai_compatible",
    base_url: str = "",
    api_key: str = "",
    models: list[dict] | None = None,
) -> dict:
    return {
        "id": provider_id or f"custom_{_slugify_provider_name(label)}_{uuid4().hex[:8]}",
        "provider_type": provider_type,
        "label": label,
        "base_url": base_url,
        "api_key": api_key,
        "models": models or [],
        "last_synced_at": None,
        "last_error": None,
    }


def _sanitize_custom_provider(provider: dict) -> dict:
    merged = _default_custom_provider(
        provider_id=provider.get("id"),
        label=provider.get("label", "自定义 Provider"),
        provider_type=provider.get("provider_type", "openai_compatible"),
        base_url=provider.get("base_url", ""),
        api_key=provider.get("api_key", ""),
        models=provider.get("models", []),
    )
    merged["last_synced_at"] = provider.get("last_synced_at")
    merged["last_error"] = provider.get("last_error")
    return merged


def provider_type_for(settings: dict, provider_id: str) -> str:
    if provider_id in settings.get("providers", {}):
        return settings["providers"][provider_id].get("provider_type", "openai_compatible")
    for row in settings.get("custom_providers", []):
        if row.get("id") == provider_id:
            return row.get("provider_type", "openai_compatible")
    return "openai_compatible"


def provider_label_for(settings: dict, provider_id: str) -> str:
    if provider_id in settings.get("providers", {}):
        return settings["providers"][provider_id].get("label", provider_id)
    for row in settings.get("custom_providers", []):
        if row.get("id") == provider_id:
            return row.get("label", provider_id)
    return provider_id


def provider_settings_for(settings: dict, provider_id: str) -> dict:
    if provider_id in settings.get("providers", {}):
        return settings["providers"][provider_id]
    for row in settings.get("custom_providers", []):
        if row.get("id") == provider_id:
            return row
    return {}


def all_provider_entries(settings: dict) -> dict[str, dict]:
    entries = {provider_id: row for provider_id, row in settings.get("providers", {}).items()}
    for row in settings.get("custom_providers", []):
        provider_id = row.get("id")
        if provider_id:
            entries[provider_id] = row
    return entries


def _infer_custom_stages(provider_type: str, model_id: str, model: dict) -> list[str]:
    explicit = model.get("stages", [])
    if explicit:
        return explicit
    if provider_type == "async_image":
        return [STEP_IMAGE_GENERATION]
    if provider_type == "gemini_native":
        return infer_stages("gemini", model_id)
    if provider_type == "openai_compatible":
        return infer_stages("deepseek", model_id)
    return []


def _sanitize_provider_models(provider_id: str, models: list[dict], *, provider_type: str | None = None) -> list[dict]:
    sanitized: list[dict] = []
    for model in models:
        model_id = model.get("id")
        if not model_id:
            continue
        if provider_id == "mock":
            stages = model.get("stages", [])
        elif provider_id not in DEFAULT_PROVIDER_SETTINGS:
            stages = _infer_custom_stages(provider_type or "openai_compatible", model_id, model)
        else:
            stages = infer_stages(provider_id, model_id)
        if not stages:
            continue
        sanitized.append(
            {
                "id": model_id,
                "label": model.get("label", model_id),
                "stages": stages,
                "compatibility": model.get("compatibility") or compatibility_for_model(provider_id, model_id),
            }
        )
    sanitized.sort(
        key=lambda row: (
            MODEL_COMPATIBILITY_ORDER.get(row.get("compatibility", "unknown"), 99),
            row.get("label", row["id"]),
        )
    )
    return sanitized


def _selection_supported(settings: dict, step: str, provider: str | None, model: str | None) -> bool:
    if not provider or not model:
        return False
    if provider == "mock":
        return True
    if provider in DEFAULT_PROVIDER_SETTINGS:
        return step in infer_stages(provider, model)
    provider_type = provider_type_for(settings, provider)
    return step in _infer_custom_stages(provider_type, model, {"id": model})


def load_global_settings() -> dict:
    ensure_dir(SETTINGS_DIR)
    if not APP_SETTINGS_PATH.exists():
        settings = default_global_settings()
        write_json(APP_SETTINGS_PATH, settings)
        return settings

    payload = read_json(APP_SETTINGS_PATH)
    settings = default_global_settings()
    if isinstance(payload, dict):
        settings["providers"].update(payload.get("providers", {}))
        settings["custom_providers"] = [
            _sanitize_custom_provider(row)
            for row in payload.get("custom_providers", [])
            if isinstance(row, dict)
        ]
        settings["defaults"].update(payload.get("defaults", {}))
        settings["prompt_templates"].update(payload.get("prompt_templates", {}))

    for provider_id, provider_settings in DEFAULT_PROVIDER_SETTINGS.items():
        settings["providers"].setdefault(provider_id, deepcopy(provider_settings))
        for field, value in provider_settings.items():
            settings["providers"][provider_id].setdefault(field, deepcopy(value))
        settings["providers"][provider_id]["models"] = _sanitize_provider_models(
            provider_id,
            settings["providers"][provider_id].get("models", []),
            provider_type=settings["providers"][provider_id].get("provider_type"),
        )

    for index, row in enumerate(settings.get("custom_providers", [])):
        provider_id = row["id"]
        settings["custom_providers"][index]["models"] = _sanitize_provider_models(
            provider_id,
            row.get("models", []),
            provider_type=row.get("provider_type"),
        )

    for step, selection in DEFAULT_STAGE_SELECTIONS.items():
        settings["defaults"].setdefault(step, deepcopy(selection))
        settings["defaults"][step].setdefault("provider", selection["provider"])
        settings["defaults"][step].setdefault("model", selection["model"])
        if not _selection_supported(
            settings,
            step,
            settings["defaults"][step].get("provider"),
            settings["defaults"][step].get("model"),
        ):
            fallback = next(iter(provider_models_for_stage(settings, step)), None)
            if fallback:
                settings["defaults"][step] = {
                    "provider": fallback["provider"],
                    "model": fallback["model"],
                }
            else:
                settings["defaults"][step] = deepcopy(selection)

    return settings


def save_global_settings(settings: dict) -> None:
    ensure_dir(SETTINGS_DIR)
    write_json(APP_SETTINGS_PATH, settings)


def update_provider_settings(
    provider_id: str,
    *,
    provider_type: str | None = None,
    label: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    models: list[dict] | None = None,
    last_synced_at: str | None | object = UNSET,
    last_error: str | None | object = UNSET,
) -> dict:
    settings = load_global_settings()
    provider_settings = None
    if provider_id in settings["providers"]:
        provider_settings = settings["providers"][provider_id]
    else:
        for row in settings.get("custom_providers", []):
            if row.get("id") == provider_id:
                provider_settings = row
                break
        if provider_settings is None:
            provider_settings = _default_custom_provider(provider_id=provider_id, label=label or provider_id)
            settings.setdefault("custom_providers", []).append(provider_settings)
    if provider_type is not None:
        provider_settings["provider_type"] = provider_type
    if label is not None:
        provider_settings["label"] = label
    if base_url is not None:
        provider_settings["base_url"] = base_url
    if api_key is not None and api_key != "":
        provider_settings["api_key"] = api_key
    if models is not None:
        provider_settings["models"] = models
    if last_synced_at is not UNSET:
        provider_settings["last_synced_at"] = last_synced_at
    if last_error is not UNSET:
        provider_settings["last_error"] = last_error
    save_global_settings(settings)
    return settings


def create_custom_provider(
    *,
    label: str,
    provider_type: str,
    base_url: str,
    api_key: str | None = None,
    models: list[dict] | None = None,
) -> dict:
    settings = load_global_settings()
    provider = _default_custom_provider(
        label=label,
        provider_type=provider_type,
        base_url=base_url,
        api_key=api_key or "",
        models=models,
    )
    settings.setdefault("custom_providers", []).append(provider)
    save_global_settings(settings)
    return settings


def delete_custom_provider(provider_id: str) -> dict:
    settings = load_global_settings()
    settings["custom_providers"] = [
        row for row in settings.get("custom_providers", []) if row.get("id") != provider_id
    ]
    for step, selection in settings.get("defaults", {}).items():
        if selection.get("provider") == provider_id:
            settings["defaults"][step] = deepcopy(DEFAULT_STAGE_SELECTIONS[step])
    save_global_settings(settings)
    return settings


def set_global_default(step: str, *, provider: str, model: str) -> dict:
    settings = load_global_settings()
    if step not in DEFAULT_STAGE_SELECTIONS:
        raise ValueError(f"Unsupported step: {step}")
    if not _selection_supported(settings, step, provider, model):
        raise ValueError(f"Unsupported default selection for {step}: {provider} / {model}")
    settings["defaults"][step] = {"provider": provider, "model": model}
    save_global_settings(settings)
    return settings


def update_prompt_templates(
    *,
    brief_system_prompt: str | None = None,
    prompt_system_prompt: str | None = None,
) -> dict:
    settings = load_global_settings()
    templates = settings.setdefault("prompt_templates", deepcopy(DEFAULT_PROMPT_TEMPLATES))
    if brief_system_prompt is not None:
        templates["brief_system_prompt"] = brief_system_prompt
    if prompt_system_prompt is not None:
        templates["prompt_system_prompt"] = prompt_system_prompt
    save_global_settings(settings)
    return settings


def resolve_stage_selection(task: dict, item: dict, settings: dict, step: str) -> dict:
    item_selection = item.get("model_overrides", {}).get(step, {})
    if _selection_supported(settings, step, item_selection.get("provider"), item_selection.get("model")):
        return {"provider": item_selection["provider"], "model": item_selection["model"], "source": "item"}

    task_selection = task.get("model_overrides", {}).get(step, {})
    if _selection_supported(settings, step, task_selection.get("provider"), task_selection.get("model")):
        return {"provider": task_selection["provider"], "model": task_selection["model"], "source": "task"}

    default_selection = settings.get("defaults", {}).get(step, DEFAULT_STAGE_SELECTIONS[step])
    if _selection_supported(settings, step, default_selection.get("provider"), default_selection.get("model")):
        return {
            "provider": default_selection["provider"],
            "model": default_selection["model"],
            "source": "global",
        }

    fallback = next(iter(provider_models_for_stage(settings, step)), None)
    if fallback:
        return {
            "provider": fallback["provider"],
            "model": fallback["model"],
            "source": "global",
        }

    return {
        "provider": DEFAULT_STAGE_SELECTIONS[step]["provider"],
        "model": DEFAULT_STAGE_SELECTIONS[step]["model"],
        "source": "global",
    }


def provider_models_for_stage(settings: dict, step: str) -> list[dict]:
    options: list[dict] = []
    for provider_id, provider_settings in all_provider_entries(settings).items():
        for model in provider_settings.get("models", []):
            if step in model.get("stages", []):
                options.append(
                    {
                        "provider": provider_id,
                        "model": model["id"],
                        "label": model.get("label", model["id"]),
                        "compatibility": model.get("compatibility", "unknown"),
                    }
                )
    options.sort(
        key=lambda option: (
            PROVIDER_ORDER.get(option["provider"], 99),
            MODEL_COMPATIBILITY_ORDER.get(option.get("compatibility", "unknown"), 99),
            option["label"],
        )
    )
    return options
