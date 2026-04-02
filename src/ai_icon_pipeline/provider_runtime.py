from __future__ import annotations

import json
from pathlib import Path

from .config import STEP_BRIEF_GENERATION, STEP_IMAGE_GENERATION, STEP_IMAGE_PROMPT
from .mock_providers import generate_brief as mock_generate_brief
from .mock_providers import generate_image_prompt as mock_generate_image_prompt
from .mock_providers import generate_images as mock_generate_images
from .providers.registry import ProviderRequestError, get_native_image_provider, get_provider
from .settings import DEFAULT_PROMPT_TEMPLATES
from .utils import ensure_dir


def _append_context_line(base: str, prefix: str, value: str) -> str:
    text = (base or "").strip()
    fragment = value.strip()
    if not fragment:
        return text
    if fragment in text:
        return text
    suffix = f"{prefix}{fragment}"
    return f"{text}\n{suffix}".strip() if text else suffix


def _merge_brief_context(*, description: str, project_background: str, style_requirements: str) -> str:
    merged = _append_context_line(description, "项目背景参考：", project_background)
    merged = _append_context_line(merged, "统一风格要求参考：", style_requirements)
    return merged


def _merge_prompt_context(*, prompt: str, project_background: str, style_requirements: str) -> str:
    merged = _append_context_line(prompt, "Project background: ", project_background)
    merged = _append_context_line(merged, "Style requirements: ", style_requirements)
    return merged


def _brief_user_prompt(**payload: str) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _prompt_user_prompt(*, brief_output: dict, style_spec: dict, runtime_config: dict) -> str:
    return json.dumps(
        {
            "brief_output": brief_output,
            "style_spec": style_spec,
            "runtime_config": runtime_config,
        },
        ensure_ascii=False,
        indent=2,
    )


def generate_brief_output(
    *,
    provider_id: str,
    provider_config: dict | None,
    api_key: str,
    model: str,
    asset_type: str,
    title: str,
    description: str,
    category: str,
    project_background: str,
    style_requirements: str,
    extra_context: str,
    system_prompt: str | None = None,
) -> dict:
    fallback = mock_generate_brief(
        asset_type=asset_type,
        title=title,
        description=description,
        category=category,
        project_background=project_background,
        style_requirements=style_requirements,
        extra_context=extra_context,
    )
    if provider_id == "mock":
        return fallback

    provider = get_provider(provider_id, provider_config)
    raw = provider.generate_json(
        api_key=api_key,
        model=model,
        system_prompt=system_prompt or DEFAULT_PROMPT_TEMPLATES["brief_system_prompt"],
        user_prompt=_brief_user_prompt(
            asset_type=asset_type,
            title=title,
            description=description,
            category=category,
            project_background=project_background,
            style_requirements=style_requirements,
            extra_context=extra_context,
        ),
    )
    merged_description = _merge_brief_context(
        description=str(raw.get("description") or fallback["description"]),
        project_background=project_background,
        style_requirements=style_requirements,
    )
    return {
        "title": str(raw.get("title") or fallback["title"]),
        "name_source": str(raw.get("name_source") or fallback["name_source"]),
        "description": merged_description,
        "keywords": raw.get("keywords") if isinstance(raw.get("keywords"), list) else fallback["keywords"],
        "icon_subject": str(raw.get("icon_subject") or fallback["icon_subject"]),
        "visual_focus": str(raw.get("visual_focus") or fallback["visual_focus"]),
        "project_background": project_background,
        "style_requirements": style_requirements,
    }


def generate_prompt_output(
    *,
    provider_id: str,
    provider_config: dict | None,
    api_key: str,
    model: str,
    brief_output: dict,
    style_spec: dict,
    runtime_config: dict,
    system_prompt: str | None = None,
) -> dict:
    fallback = mock_generate_image_prompt(
        brief_output=brief_output,
        style_spec=style_spec,
        runtime_config=runtime_config,
    )
    if provider_id == "mock":
        return fallback

    provider = get_provider(provider_id, provider_config)
    raw = provider.generate_json(
        api_key=api_key,
        model=model,
        system_prompt=system_prompt or DEFAULT_PROMPT_TEMPLATES["prompt_system_prompt"],
        user_prompt=_prompt_user_prompt(
            brief_output=brief_output,
            style_spec=style_spec,
            runtime_config=runtime_config,
        ),
    )
    project_background = str(brief_output.get("project_background", "") or "")
    style_requirements = str(brief_output.get("style_requirements", "") or "")
    merged_prompt = _merge_prompt_context(
        prompt=str(raw.get("prompt") or fallback["prompt"]),
        project_background=project_background,
        style_requirements=style_requirements,
    )
    return {
        "prompt": merged_prompt,
        "negative_prompt": str(raw.get("negative_prompt") or fallback["negative_prompt"]),
        "constraints": fallback["constraints"],
        "batch_context": {
            "project_background": project_background,
            "style_requirements": style_requirements,
        },
    }


def generate_image_candidates(
    *,
    provider_id: str,
    provider_config: dict | None,
    api_key: str,
    model: str,
    output_dir: Path,
    version: str,
    candidate_count: int,
    prompt: str,
    negative_prompt: str,
    image_size: str,
    image_aspect_ratio: str,
    image_resolution: str,
) -> list[dict]:
    if provider_id == "mock":
        return mock_generate_images(output_dir=output_dir, version=version, candidate_count=candidate_count)

    if provider_id != "gemini" and (provider_config or {}).get("provider_type") != "gemini_native":
        raise ValueError(f"Provider '{provider_id}' does not support image generation yet")

    provider = get_native_image_provider(provider_id, provider_config)
    composed_prompt = prompt
    if negative_prompt:
        composed_prompt += f"\nAvoid: {negative_prompt}"

    try:
        image_bytes = provider.generate_images(
            api_key=api_key,
            model=model,
            prompt=composed_prompt,
            count=candidate_count,
            aspect_ratio=image_aspect_ratio,
            image_resolution=image_resolution,
        )
    except ProviderRequestError as exc:
        if candidate_count > 1 and "Multiple candidates is not enabled" in str(exc):
            image_bytes = []
            for _ in range(candidate_count):
                image_bytes.extend(
                    provider.generate_images(
                        api_key=api_key,
                        model=model,
                        prompt=composed_prompt,
                        count=1,
                        aspect_ratio=image_aspect_ratio,
                        image_resolution=image_resolution,
                    )
                )
        else:
            raise

    ensure_dir(output_dir)
    candidates = []
    for index, payload in enumerate(image_bytes, start=1):
        filename = f"{version}_candidate_{index:02d}.png"
        path = output_dir / filename
        path.write_bytes(payload)
        candidates.append(
            {
                "candidate_id": f"candidate_{index:02d}",
                "image_path": str(path.name),
            }
        )
    return candidates
