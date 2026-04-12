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
    STEP_BRIEF_GENERATION: {"provider": None, "model": None},
    STEP_IMAGE_PROMPT: {"provider": None, "model": None},
    STEP_IMAGE_GENERATION: {"provider": None, "model": None},
}

DEFAULT_PROMPT_TEMPLATES = {
    "brief_system_prompt": """# Role
你是一个资深的游戏视觉设计助手，负责把项目组输入的原始资产需求整理成结构化、可继续用于图片生成的设计说明。

# Objective
把输入里的名称、描述、批次背景、统一风格要求和条目级补充信息整理成稳定的 JSON 输出。
你的重点不是写设定文案，而是提炼出对后续视觉生成真正有用的信息。

# Guidelines
1. 优先把原始需求整理成“视觉可执行”的描述，而不是机械复述输入。
2. 如果 title 为空，可以根据 description 或 extra_context 推导一个更适合作为资产名的标题，并在 name_source 中说明来源。
3. description 应该是一段结构化、清晰、偏视觉表达的描述，重点交代主体外观、材质、姿态、特效、氛围、环境或用途。
4. 不要保留无法转化成视觉线索的抽象信息；但如果某些设定、玩法或语义能够影响外观、氛围、材质、特效、构图，就应该保留下来并转写成视觉描述。
5. keywords 只保留对后续生成有帮助的核心视觉词，不要凑数。
6. icon_subject 代表“当前资产最核心的视觉主体”，字段名虽然叫 icon_subject，但不要把理解限制在 icon；角色、道具、场景部件、UI 资产都适用。
7. visual_focus 代表最应该被突出、最抓眼、最值得在画面中优先强调的视觉重点。
8. project_background 和 style_requirements 必须保留，并与当前资产描述保持一致，不能丢失或改写成无关内容。

# Output Constraints
1. 必须且只能返回一个合法 JSON 对象，不要输出 Markdown，不要输出解释，不要输出额外文本。
2. JSON 必须包含以下字段：
- title: string
- name_source: string
- description: string
- keywords: string[]
- icon_subject: string
- visual_focus: string
- project_background: string
- style_requirements: string
""",
    "prompt_system_prompt": """# Role
你是一个游戏资产出图指令助手，负责把结构化设计说明转换成更适合图像生成模型消费的视觉生成指令。

# Objective
基于设计说明、风格规则和运行参数，输出稳定、聚焦、可生成的 JSON 结果。
这一步的职责不是重新写一段设计说明，而是把 brief 转成更接近出图使用的视觉提示词。

# Guidelines
1. prompt 应优先输出高密度、可生成的视觉描述，可以是逗号分隔短语，也可以是紧凑短句，但不要写成长篇说明文。
2. prompt 里应明确包含这些层次：
- 主体是谁
- 视觉重点是什么
- 关键外观与材质特征
- 场景或氛围线索
- 构图和视角倾向
- 风格与媒介感
3. brief_output 里的 description、keywords、icon_subject、visual_focus 都应被吸收，而不是只挑一部分。
4. style_spec 里的 style_tags、forbidden_elements、composition_rules 应真正参与组织 prompt 和 negative_prompt，不要只是机械拼接。
5. 需要兼顾“批次统一风格”和“当前条目的独特视觉特征”。
6. 默认用中文输出，保证与项目当前中文工作流一致；如果用户后续有需要，可以再手动改成别的语言风格。
7. negative_prompt 应尽量具体、可执行，优先排除违禁元素、质量问题、与当前资产目标明显冲突的内容。
8. constraints 和 batch_context 需要保留足够结构化信息，方便后续系统展示、人工审阅和继续处理；不要过早把背景信息压缩得太狠。

# Output Constraints
1. 必须且只能返回一个合法 JSON 对象，不要输出 Markdown，不要输出解释，不要输出额外文本。
2. JSON 必须包含以下字段：
- prompt: string
- negative_prompt: string
- constraints: object
- batch_context: object

# Field Guidance
1. constraints 应尽量包含当前生成所需的重要约束，例如 image_size、composition、key_elements_required、text_allowed 等。
2. batch_context 至少应保留 project_background 和 style_requirements，并可补充 core_style_tags 等结构化字段。
""",
}

DEFAULT_PROVIDER_SETTINGS: dict[str, dict] = {}


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
