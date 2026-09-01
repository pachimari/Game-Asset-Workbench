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
    "brief_system_prompt": """你是资深游戏美术策划与技术美术协作助手。你的任务是把原始资产需求整理成适合后续图片生成的结构化设计说明。

目标：
1. 把混乱、抽象、口语化的需求整理成稳定的视觉说明。
2. 如果用户输入主要描述的是技能效果、机制、元素属性或抽象感觉，而没有明确视觉主体，你必须补足成可画出来的视觉对象、材质、能量形态、光效或构图线索。
3. 只保留能够转化为视觉线索的信息；无法影响外观、氛围、材质、特效、构图的抽象信息不要保留。
4. 必须继承并保留批次级 project_background 和 style_requirements。

处理规则：
- title 为空时，结合 description / extra_context 推导一个标准化名称，并在 name_source 说明来源。
- description 要写成面向视觉生成的结构化说明，重点描述主体、材质、动作、能量表现、构图重点、光效氛围。
- keywords 输出 5-8 个高价值视觉关键词，不要输出空泛形容词堆砌。
- icon_subject 虽然字段名叫 icon_subject，但语义上表示当前资产最核心的视觉主体，不要把它限制成“图标”。
- visual_focus 表示画面里最应该被强调的视觉重点，例如核心武器、能量团、法阵、护盾边缘高光、人物姿态、主符号等。
- 对技能、阵法、法术、状态类需求，如果原始输入只有效果描述，必须把它具象化成“画面里真正能看到的东西”。
- 不要扩写剧情，不要写玩法说明，不要写数值，不要写解释性废话。

输出要求：
- 只能返回合法 JSON
- 不要输出 Markdown
- 不要输出解释文字

JSON 字段必须包含：
- title: string
- name_source: string
- description: string
- keywords: string[]
- icon_subject: string
- visual_focus: string
- project_background: string
- style_requirements: string
""",
    "prompt_system_prompt": """你是游戏资产出图指令工程师。你的任务是把结构化设计说明转成真正适合图像模型消费的高密度视觉提示词。

目标：
1. 输出专业、具体、可生成的视觉语言。
2. 不要口语化，不要写“亮闪闪的”“有那种感觉”“符号化一点”这类无效表达。
3. 默认输出中文，但要保持结构清楚、词汇专业、视觉信息密度高。
4. 必须把批次背景、统一风格、构图规则和运行时规格吸收进 prompt，而不是简单复述。

处理规则：
- prompt 要优先描述：主体、视觉重点、关键材质/细节、环境氛围、构图方式、光效、风格。
- 可以用高密度短语，也可以用紧凑短句，但不要写成松散说明文。
- 要兼顾统一批次风格与单条资产特征。
- style_spec 中的 style_tags、forbidden_elements、composition_rules 要真正被吸收，而不是机械拼接。
- 如果 runtime_config 中有长宽比、分辨率、候选数量等约束，要把对画面结构有影响的内容自然融入 prompt/constraints。
- negative_prompt 要具体、实用，优先约束文字、水印、低质结构、错误解剖、脏乱背景、破坏主题的信息。
- batch_context 要保留批次背景和风格要求，不要过早压缩成模糊摘要。

输出要求：
- 只能返回合法 JSON
- 不要输出 Markdown
- 不要输出解释文字

JSON 字段必须包含：
- prompt: string
- negative_prompt: string
- constraints: object
- batch_context: object

# Field Guidance
1. constraints 应尽量包含当前生成所需的重要约束，例如 image_size、composition、key_elements_required、text_allowed 等。
2. batch_context 至少应保留 project_background 和 style_requirements，并可补充 core_style_tags 等结构化字段。
""",
    "grid_sheet_prompt_template": """Create one complete game asset icon grid sheet.

Canvas and grid:
- Exact grid: {{rows}} rows x {{cols}} columns, {{cell_count}} equal cells.
- Fill cells in row-major order from left to right, top to bottom.
- The grid occupies the full image canvas from edge to edge with no decorative outer frame or extra border margin.
- Keep cells visually separated with clean empty gutters only. Do not draw ornate frames, card borders, labels, badges, or decorative grid art.
- Each cell must contain exactly one independent asset subject.
- Do not let any subject cross cell boundaries.
- Do not add text, labels, numbering, watermarks, logos, signatures, captions, UI badges, or extra symbols.

Cropping safety:
- Assume the image will be split by a strict mathematical {{rows}} x {{cols}} overlay after generation.
- Align all cell boundaries to equal mathematical divisions of the full canvas.
- Keep every subject centered inside its own cell with enough safe margin so no part of the subject touches or crosses the crop boundary.
- Avoid merged cells, uneven cell sizes, panoramic compositions, shared backgrounds, or subjects spanning multiple cells.

Style:
- Project background: {{project_background}}
- Unified style requirements: {{style_requirements}}
- Use consistent camera angle, lighting, material rendering, background treatment, and icon scale across the whole sheet.
- Prefer centered subjects, readable silhouettes, and simple backgrounds suitable for later tile cropping.

Cell assignments:
{{slot_lines}}

Empty cells:
- If the grid has more cells than assignments, keep remaining cells visually empty and unobtrusive.
""",
    "grid_sheet_negative_prompt": (
        "text, labels, numbers, watermark, signature, logo, subject crossing cell boundaries, "
        "merged cells, uneven grid, inconsistent cell sizes, panoramic composition, shared scene, "
        "duplicated unrelated objects, busy background, cropped subject"
    ),
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
    protocol_variant: str = "generic",
    base_url: str = "",
    api_key: str = "",
    models: list[dict] | None = None,
    image_max_concurrency: int | None = None,
) -> dict:
    return {
        "id": provider_id or f"custom_{_slugify_provider_name(label)}_{uuid4().hex[:8]}",
        "provider_type": provider_type,
        "protocol_variant": protocol_variant or "generic",
        "label": label,
        "base_url": base_url,
        "api_key": api_key,
        "models": models or [],
        "image_max_concurrency": image_max_concurrency,
        "last_synced_at": None,
        "last_error": None,
    }


def _sanitize_custom_provider(provider: dict) -> dict:
    raw_concurrency = provider.get("image_max_concurrency")
    try:
        image_max_concurrency = int(raw_concurrency) if raw_concurrency not in (None, "") else None
    except (TypeError, ValueError):
        image_max_concurrency = None
    if image_max_concurrency is not None and image_max_concurrency < 1:
        image_max_concurrency = 1
    merged = _default_custom_provider(
        provider_id=provider.get("id"),
        label=provider.get("label", "自定义 Provider"),
        provider_type=provider.get("provider_type", "openai_compatible"),
        protocol_variant=provider.get("protocol_variant", "generic"),
        base_url=provider.get("base_url", ""),
        api_key=provider.get("api_key", ""),
        models=provider.get("models", []),
        image_max_concurrency=image_max_concurrency,
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
    protocol_variant: str | None = None,
    label: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    models: list[dict] | None = None,
    image_max_concurrency: int | None | object = UNSET,
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
    if protocol_variant is not None:
        provider_settings["protocol_variant"] = protocol_variant or "generic"
    if label is not None:
        provider_settings["label"] = label
    if base_url is not None:
        provider_settings["base_url"] = base_url
    if api_key is not None and api_key != "":
        provider_settings["api_key"] = api_key
    if models is not None:
        provider_settings["models"] = models
    if image_max_concurrency is not UNSET:
        provider_settings["image_max_concurrency"] = image_max_concurrency
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
    protocol_variant: str = "generic",
    base_url: str,
    api_key: str | None = None,
    models: list[dict] | None = None,
    image_max_concurrency: int | None = None,
) -> dict:
    settings = load_global_settings()
    provider = _default_custom_provider(
        label=label,
        provider_type=provider_type,
        protocol_variant=protocol_variant,
        base_url=base_url,
        api_key=api_key or "",
        models=models,
        image_max_concurrency=image_max_concurrency,
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
    grid_sheet_prompt_template: str | None = None,
    grid_sheet_negative_prompt: str | None = None,
) -> dict:
    settings = load_global_settings()
    templates = settings.setdefault("prompt_templates", deepcopy(DEFAULT_PROMPT_TEMPLATES))
    if brief_system_prompt is not None:
        templates["brief_system_prompt"] = brief_system_prompt
    if prompt_system_prompt is not None:
        templates["prompt_system_prompt"] = prompt_system_prompt
    if grid_sheet_prompt_template is not None:
        templates["grid_sheet_prompt_template"] = grid_sheet_prompt_template
    if grid_sheet_negative_prompt is not None:
        templates["grid_sheet_negative_prompt"] = grid_sheet_negative_prompt
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
