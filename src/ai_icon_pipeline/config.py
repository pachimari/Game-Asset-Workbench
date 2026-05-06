from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TASKS_DIR = PROJECT_ROOT / "tasks"


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


API_ALLOW_REMOTE = _env_flag("AI_ICON_PIPELINE_API_ALLOW_REMOTE", default=False)
API_TOKEN = os.getenv("AI_ICON_PIPELINE_API_TOKEN", "").strip()
API_PUBLIC_ERROR_DETAILS = _env_flag("AI_ICON_PIPELINE_API_PUBLIC_ERROR_DETAILS", default=False)
API_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("AI_ICON_PIPELINE_API_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
GENERATING_STALE_SECONDS = int(os.getenv("AI_ICON_PIPELINE_GENERATING_STALE_SECONDS", "1800"))
ASYNC_IMAGE_SUPPLEMENTAL_MODELS = tuple(
    model_id.strip()
    for model_id in os.getenv(
        "AI_ICON_PIPELINE_ASYNC_IMAGE_SUPPLEMENTAL_MODELS",
        os.getenv(
            "AI_ICON_PIPELINE_TOAPIS_SUPPLEMENTAL_IMAGE_MODELS",
            "gemini-3.1-flash-image-preview,gpt-image-2",
        ),
    ).split(",")
    if model_id.strip()
)

STEP_BRIEF_GENERATION = "brief_generation"
STEP_IMAGE_PROMPT = "image_prompt"
STEP_IMAGE_GENERATION = "image_generation"

STATUS_DRAFT = "draft"
STATUS_BRIEF_GENERATING = "brief_generating"
STATUS_BRIEF_GENERATED = "brief_generated"
STATUS_BRIEF_APPROVED = "brief_approved"
STATUS_PROMPT_GENERATING = "prompt_generating"
STATUS_PROMPT_GENERATED = "prompt_generated"
STATUS_PROMPT_APPROVED = "prompt_approved"
STATUS_IMAGE_GENERATING = "image_generating"
STATUS_IMAGE_GENERATED = "image_generated"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_ARCHIVED = "archived"

DEFAULT_STYLE_SPEC = {
    "style_preset_id": "default",
    "style_tags": ["fantasy", "high contrast", "clean silhouette"],
    "forbidden_elements": ["text", "watermark", "complex background"],
    "composition_rules": [
        "single centered subject",
        "clear silhouette",
        "sufficient negative space",
    ],
    "background_rules": {
        "mode": "simple_or_removable",
        "transparent_preferred": False,
    },
    "post_process_rules": ["resize_512", "optional_bg_cleanup"],
}

DEFAULT_RUNTIME_CONFIG = {
    "brief_provider": None,
    "prompt_provider": None,
    "image_provider": None,
    "candidate_count": 1,
    "image_size": "512x512",
    "image_aspect_ratio": "1:1",
    "image_resolution": "1K",
}

IMAGE_ASPECT_RATIO_OPTIONS = ["1:1", "3:4", "4:3", "2:3", "3:2", "9:16", "16:9", "21:9"]
IMAGE_RESOLUTION_OPTIONS = ["auto", "512", "1K", "2K", "4K"]

# 1x1 transparent PNG.
PLACEHOLDER_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/w8AAgMBAp0X7xwAAAAASUVORK5CYII="
)
