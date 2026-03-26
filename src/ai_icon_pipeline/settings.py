from __future__ import annotations

from copy import deepcopy
from pathlib import Path

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
        "api_key": "",
        "models": [],
        "last_synced_at": None,
        "last_error": None,
    },
    "deepseek": {
        "api_key": "",
        "models": [],
        "last_synced_at": None,
        "last_error": None,
    },
    "mock": {
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
        "defaults": deepcopy(DEFAULT_STAGE_SELECTIONS),
        "prompt_templates": deepcopy(DEFAULT_PROMPT_TEMPLATES),
    }


def _sanitize_provider_models(provider_id: str, models: list[dict]) -> list[dict]:
    sanitized: list[dict] = []
    for model in models:
        model_id = model.get("id")
        if not model_id:
            continue
        if provider_id == "mock":
            stages = model.get("stages", [])
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


def _selection_supported(step: str, provider: str | None, model: str | None) -> bool:
    if not provider or not model:
        return False
    return step in infer_stages(provider, model) or provider == "mock"


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
        settings["defaults"].update(payload.get("defaults", {}))
        settings["prompt_templates"].update(payload.get("prompt_templates", {}))

    for provider_id, provider_settings in DEFAULT_PROVIDER_SETTINGS.items():
        settings["providers"].setdefault(provider_id, deepcopy(provider_settings))
        for field, value in provider_settings.items():
            settings["providers"][provider_id].setdefault(field, deepcopy(value))
        settings["providers"][provider_id]["models"] = _sanitize_provider_models(
            provider_id,
            settings["providers"][provider_id].get("models", []),
        )

    for step, selection in DEFAULT_STAGE_SELECTIONS.items():
        settings["defaults"].setdefault(step, deepcopy(selection))
        settings["defaults"][step].setdefault("provider", selection["provider"])
        settings["defaults"][step].setdefault("model", selection["model"])
        if not _selection_supported(
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
    api_key: str | None = None,
    models: list[dict] | None = None,
    last_synced_at: str | None = None,
    last_error: str | None = None,
) -> dict:
    settings = load_global_settings()
    provider_settings = settings["providers"].setdefault(
        provider_id,
        deepcopy(DEFAULT_PROVIDER_SETTINGS.get(provider_id, {"api_key": "", "models": [], "last_synced_at": None, "last_error": None})),
    )
    if api_key is not None:
        provider_settings["api_key"] = api_key
    if models is not None:
        provider_settings["models"] = models
    if last_synced_at is not None:
        provider_settings["last_synced_at"] = last_synced_at
    if last_error is not None:
        provider_settings["last_error"] = last_error
    save_global_settings(settings)
    return settings


def set_global_default(step: str, *, provider: str, model: str) -> dict:
    settings = load_global_settings()
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
    if _selection_supported(step, item_selection.get("provider"), item_selection.get("model")):
        return {"provider": item_selection["provider"], "model": item_selection["model"], "source": "item"}

    task_selection = task.get("model_overrides", {}).get(step, {})
    if _selection_supported(step, task_selection.get("provider"), task_selection.get("model")):
        return {"provider": task_selection["provider"], "model": task_selection["model"], "source": "task"}

    default_selection = settings.get("defaults", {}).get(step, DEFAULT_STAGE_SELECTIONS[step])
    if _selection_supported(step, default_selection.get("provider"), default_selection.get("model")):
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
    for provider_id, provider_settings in settings.get("providers", {}).items():
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
