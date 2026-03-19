from __future__ import annotations

from pathlib import Path

from .utils import write_placeholder_png


def _derive_title(description: str, title: str, asset_type: str) -> str:
    if title:
        return title
    cleaned = description.strip().replace("，", "").replace("。", "")
    prefix = cleaned[:8] if cleaned else "图标"
    suffix_map = {
        "skill_icon": "技能",
        "buff_icon": "状态",
        "item_icon": "道具",
    }
    return f"{prefix}{suffix_map.get(asset_type, '图标')}"


def generate_brief(
    *,
    asset_type: str,
    title: str,
    description: str,
    category: str,
    project_background: str,
    style_requirements: str,
    extra_context: str,
) -> dict:
    resolved_title = _derive_title(description, title, asset_type)
    resolved_description = (
        f"{resolved_title}：面向{asset_type}，"
        f"围绕“{description}”整理成适合图标生成的简明需求。"
    )
    if project_background:
        resolved_description += f" 项目背景参考：{project_background}"
    if style_requirements:
        resolved_description += f" 统一风格要求参考：{style_requirements}"
    if extra_context:
        resolved_description += f" 额外上下文：{extra_context}"
    keywords = [
        asset_type,
        category or "general",
        project_background[:8] or "project",
        description[:8] or "icon",
    ]
    return {
        "title": resolved_title,
        "name_source": "user_input" if title else "derived_from_description",
        "description": resolved_description,
        "keywords": keywords,
        "icon_subject": f"{resolved_title} 的核心视觉符号",
        "visual_focus": f"突出{asset_type}的核心视觉识别点",
    }


def generate_image_prompt(*, brief_output: dict, style_spec: dict, runtime_config: dict) -> dict:
    style_tags = ", ".join(style_spec["style_tags"])
    forbidden = ", ".join(style_spec["forbidden_elements"])
    composition = ", ".join(style_spec["composition_rules"])
    prompt = (
        f"game icon asset, name: {brief_output['title']}, "
        f"subject: {brief_output.get('icon_subject', brief_output['title'])}, "
        f"{brief_output['description']}, "
        f"keywords: {', '.join(brief_output['keywords'])}, "
        f"visual focus: {brief_output['visual_focus']}, "
        f"style: {style_tags}, composition: {composition}"
    )
    negative_prompt = f"forbidden: {forbidden}"
    return {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "constraints": {
            "candidate_count": runtime_config["candidate_count"],
            "image_size": runtime_config["image_size"],
            "text_allowed": False,
        },
    }


def generate_images(*, output_dir: Path, version: str, candidate_count: int) -> list[dict]:
    candidates = []
    for index in range(1, candidate_count + 1):
        filename = f"{version}_candidate_{index:02d}.png"
        path = output_dir / filename
        write_placeholder_png(path)
        candidates.append(
            {
                "candidate_id": f"candidate_{index:02d}",
                "image_path": str(path.name),
            }
        )
    return candidates
