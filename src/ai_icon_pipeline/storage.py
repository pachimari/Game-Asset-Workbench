from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re
import shutil
import time
import zipfile
import csv
from io import StringIO

from .config import (
    DEFAULT_RUNTIME_CONFIG,
    DEFAULT_STYLE_SPEC,
    GENERATING_STALE_SECONDS,
    GRID_SLOT_STRATEGY_OPTIONS,
    IMAGE_GENERATION_MODE_OPTIONS,
    STATUS_FAILED,
    STATUS_DRAFT,
    STATUS_BRIEF_GENERATING,
    STATUS_COMPLETED,
    STATUS_IMAGE_GENERATED,
    STATUS_PROMPT_GENERATING,
    STATUS_IMAGE_GENERATING,
    STEP_BRIEF_GENERATION,
    STEP_IMAGE_GENERATION,
    STEP_IMAGE_PROMPT,
    TASKS_DIR,
)
from .utils import ensure_dir, utc_now


TASK_ID_PATTERN = re.compile(r"^task_(\d+)$")
ITEM_ID_PATTERN = re.compile(r"^item_(\d+)$")
PENDING_ASYNC_STATUSES = {"queued", "submitted", "processing", "pending", "running", "in_progress"}
LOCK_RETRY_SECONDS = 0.05
LOCK_TIMEOUT_SECONDS = 10.0


def _bounded_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    try:
        resolved = int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        resolved = default
    return min(max(resolved, minimum), maximum)


def default_model_overrides() -> dict:
    return {
        STEP_BRIEF_GENERATION: {"provider": None, "model": None},
        STEP_IMAGE_PROMPT: {"provider": None, "model": None},
        STEP_IMAGE_GENERATION: {"provider": None, "model": None},
    }


def default_item_runtime_overrides() -> dict:
    return {
        "image_aspect_ratio": None,
        "image_resolution": None,
    }


def default_starred_image_versions() -> list[str]:
    return []


def normalize_runtime_config(runtime_config: dict | None) -> dict:
    merged = deepcopy(DEFAULT_RUNTIME_CONFIG)
    if isinstance(runtime_config, dict):
        merged.update(runtime_config)
    # 产品语义调整：候选图按“每次生成 1 张、历史累积”工作，不再一次批量吐多张。
    merged["candidate_count"] = 1
    if merged.get("image_generation_mode") not in IMAGE_GENERATION_MODE_OPTIONS:
        merged["image_generation_mode"] = DEFAULT_RUNTIME_CONFIG["image_generation_mode"]
    if merged.get("grid_slot_strategy") not in GRID_SLOT_STRATEGY_OPTIONS:
        merged["grid_slot_strategy"] = DEFAULT_RUNTIME_CONFIG["grid_slot_strategy"]
    raw_references = merged.get("sheet_reference_images")
    if not isinstance(raw_references, list):
        raw_references = []
    merged["sheet_reference_images"] = [
        str(value).strip() for value in raw_references if isinstance(value, str) and str(value).strip()
    ][:16]
    merged["grid_rows"] = _bounded_int(merged.get("grid_rows"), default=8, minimum=1, maximum=12)
    merged["grid_cols"] = _bounded_int(merged.get("grid_cols"), default=8, minimum=1, maximum=12)
    merged["grid_padding"] = _bounded_int(merged.get("grid_padding"), default=0, minimum=0, maximum=512)
    merged["grid_gap"] = _bounded_int(merged.get("grid_gap"), default=0, minimum=0, maximum=512)
    merged["grid_cell_count"] = merged["grid_rows"] * merged["grid_cols"]
    return merged


def ensure_tasks_root() -> None:
    ensure_dir(TASKS_DIR)


def task_dir(task_id: str) -> Path:
    return TASKS_DIR / task_id


def item_dir(task_id: str, item_id: str) -> Path:
    return task_dir(task_id) / "items" / item_id


def read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict | list) -> None:
    ensure_dir(path.parent)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def append_jsonl(path: Path, payload: dict) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _safe_path_fragment(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:80] or "untitled"


def _parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _elapsed_seconds(start: str | None, end: str | None = None) -> float | None:
    start_at = _parse_utc_timestamp(start)
    if not start_at:
        return None
    end_at = _parse_utc_timestamp(end) if end else datetime.now(timezone.utc)
    if not end_at:
        end_at = datetime.now(timezone.utc)
    return max(0.0, (end_at - start_at).total_seconds())


def next_task_id() -> str:
    ensure_tasks_root()
    max_id = 0
    for child in TASKS_DIR.iterdir():
        if child.is_dir():
            match = TASK_ID_PATTERN.match(child.name)
            if match:
                max_id = max(max_id, int(match.group(1)))
    return f"task_{max_id + 1:03d}"


def _next_item_id(items: list[dict]) -> str:
    max_id = 0
    for item in items:
        match = ITEM_ID_PATTERN.match(item["item_id"])
        if match:
            max_id = max(max_id, int(match.group(1)))
    return f"item_{max_id + 1:03d}"


@contextmanager
def _task_operation_lock(task_id: str):
    lock_path = task_dir(task_id) / ".task.lock"
    ensure_dir(lock_path.parent)
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for task lock: {task_id}")
            time.sleep(LOCK_RETRY_SECONDS)
    try:
        os.write(fd, str(os.getpid()).encode("utf-8"))
        yield
    finally:
        os.close(fd)
        try:
            os.unlink(lock_path)
        except FileNotFoundError:
            pass


def _normalize_item(raw_item: dict, item_id: str, timestamp: str) -> dict:
    return {
        "item_id": item_id,
        "asset_type": raw_item.get("asset_type", "generic_icon"),
        "title": raw_item.get("title", ""),
        "description": raw_item.get("description", ""),
        "category": raw_item.get("category", ""),
        "extra_context": raw_item.get("extra_context", ""),
        "status": STATUS_DRAFT,
        "created_at": timestamp,
        "updated_at": timestamp,
        "starred_image_versions": list(raw_item.get("starred_image_versions", default_starred_image_versions())),
        "current_versions": {
            "brief_generation": None,
            "image_prompt": None,
            "image_generation": None,
        },
        "model_overrides": deepcopy(raw_item.get("model_overrides", default_model_overrides())),
        "runtime_overrides": deepcopy(raw_item.get("runtime_overrides", default_item_runtime_overrides())),
    }


def _ensure_task_schema(task: dict) -> dict:
    task.setdefault("items", [])
    task.setdefault("item_count", len(task["items"]))
    task.setdefault("status", STATUS_DRAFT)
    task.setdefault("model_overrides", deepcopy(default_model_overrides()))
    for step, selection in default_model_overrides().items():
        task["model_overrides"].setdefault(step, deepcopy(selection))
        task["model_overrides"][step].setdefault("provider", None)
        task["model_overrides"][step].setdefault("model", None)
    return task


def _ensure_item_schema(item: dict) -> dict:
    item.setdefault("model_overrides", deepcopy(default_model_overrides()))
    for step, selection in default_model_overrides().items():
        item["model_overrides"].setdefault(step, deepcopy(selection))
        item["model_overrides"][step].setdefault("provider", None)
        item["model_overrides"][step].setdefault("model", None)
    item.setdefault("runtime_overrides", deepcopy(default_item_runtime_overrides()))
    for key, value in default_item_runtime_overrides().items():
        item["runtime_overrides"].setdefault(key, value)
    item.setdefault("starred_image_versions", list(default_starred_image_versions()))
    return item


def _mark_item_failed(task_id: str, item_id: str, item: dict, *, reason: str) -> dict:
    item["status"] = STATUS_FAILED
    save_item(task_id, item)
    metrics = load_metrics(task_id, item_id)
    metrics["status"] = STATUS_FAILED
    metrics["end_time"] = utc_now()
    save_metrics(task_id, item_id, metrics)
    event = {
        "timestamp": utc_now(),
        "source": "system",
        "action": "recover_stale_generation",
        "item_id": item_id,
        "reason": reason,
        "to": STATUS_FAILED,
    }
    append_item_event(task_id, item_id, event)
    append_event(task_id, event)
    refresh_task_summary(task_id)
    return item


def reconcile_item_generating_state(task_id: str, item_id: str, item: dict) -> dict:
    status = item.get("status")
    if status not in {STATUS_BRIEF_GENERATING, STATUS_PROMPT_GENERATING, STATUS_IMAGE_GENERATING}:
        return item

    updated_at = _parse_utc_timestamp(item.get("updated_at"))
    if not updated_at:
        return item
    age_seconds = (datetime.now(timezone.utc) - updated_at).total_seconds()
    if age_seconds < GENERATING_STALE_SECONDS:
        return item

    if status == STATUS_IMAGE_GENERATING:
        pending_versions = 0
        for artifact_meta in list_artifacts(task_id, item_id, STEP_IMAGE_GENERATION):
            artifact = artifact_meta.get("_payload")
            if not isinstance(artifact, dict):
                artifact = load_artifact(task_id, item_id, STEP_IMAGE_GENERATION, artifact_meta["version"])
            async_status = str((artifact.get("async_job") or {}).get("status", "")).lower()
            if async_status in PENDING_ASYNC_STATUSES:
                pending_versions += 1
        if pending_versions > 0:
            return item

    return _mark_item_failed(task_id, item_id, item, reason=f"stale_{status}")


def create_task(
    *,
    task_name: str,
    project_background: str = "",
    style_requirements: str = "",
    items: list[dict] | None = None,
    asset_domain: str = "game_icon_assets",
    style_spec: dict | None = None,
    runtime_config: dict | None = None,
    task_id: str | None = None,
) -> dict:
    ensure_tasks_root()
    resolved_task_id = task_id or next_task_id()
    root = task_dir(resolved_task_id)
    if root.exists():
        raise ValueError(f"Task already exists: {resolved_task_id}")
    ensure_dir(root / "configs")
    ensure_dir(root / "items")
    ensure_dir(root / "exports")

    now = utc_now()
    raw_items = items or []
    normalized_items = []
    for raw_item in raw_items:
        item_id = raw_item.get("item_id") or _next_item_id(normalized_items)
        item = _normalize_item(raw_item, item_id, now)
        normalized_items.append(item)
        _create_item_files(resolved_task_id, item)

    task = {
        "task_id": resolved_task_id,
        "task_name": task_name,
        "project_background": project_background,
        "style_requirements": style_requirements,
        "asset_domain": asset_domain,
        "created_at": now,
        "updated_at": now,
        "status": "draft",
        "items": [item["item_id"] for item in normalized_items],
        "item_count": len(normalized_items),
        "style_spec_ref": "configs/style_spec.json",
        "runtime_config_ref": "configs/runtime_config.json",
        "model_overrides": deepcopy(default_model_overrides()),
    }

    write_json(root / "task.json", task)
    write_json(root / "configs" / "style_spec.json", deepcopy(style_spec or DEFAULT_STYLE_SPEC))
    write_json(
        root / "configs" / "runtime_config.json",
        normalize_runtime_config(runtime_config),
    )
    append_event(
        resolved_task_id,
        {
            "timestamp": now,
            "source": "system",
            "action": "create_task",
            "to": "draft",
            "item_count": len(normalized_items),
        },
    )
    refresh_task_summary(resolved_task_id)
    return load_task(resolved_task_id)


def delete_task(task_id: str) -> None:
    if not TASK_ID_PATTERN.match(task_id):
        raise ValueError(f"Invalid task id: {task_id}")
    root = task_dir(task_id)
    if root.parent != TASKS_DIR or root == TASKS_DIR:
        raise ValueError(f"Refusing to delete unsafe task path: {root}")
    if not root.exists():
        raise ValueError(f"Task not found: {task_id}")
    shutil.rmtree(root)


def update_runtime_config(
    task_id: str,
    *,
    candidate_count: int | None = None,
    image_size: str | None = None,
    image_aspect_ratio: str | None = None,
    image_resolution: str | None = None,
    image_generation_mode: str | None = None,
    grid_rows: int | None = None,
    grid_cols: int | None = None,
    grid_padding: int | None = None,
    grid_gap: int | None = None,
    grid_slot_strategy: str | None = None,
    sheet_reference_images: list[str] | None = None,
) -> dict:
    current = load_runtime_config(task_id)
    merged = normalize_runtime_config(current)
    if image_size is not None:
        merged["image_size"] = image_size
    if image_aspect_ratio is not None:
        merged["image_aspect_ratio"] = image_aspect_ratio
    if image_resolution is not None:
        merged["image_resolution"] = image_resolution
    if image_generation_mode is not None:
        if image_generation_mode not in IMAGE_GENERATION_MODE_OPTIONS:
            raise ValueError(f"Unsupported image_generation_mode: {image_generation_mode}")
        merged["image_generation_mode"] = image_generation_mode
    if grid_rows is not None:
        merged["grid_rows"] = grid_rows
    if grid_cols is not None:
        merged["grid_cols"] = grid_cols
    if grid_padding is not None:
        merged["grid_padding"] = grid_padding
    if grid_gap is not None:
        merged["grid_gap"] = grid_gap
    if grid_slot_strategy is not None:
        if grid_slot_strategy not in GRID_SLOT_STRATEGY_OPTIONS:
            raise ValueError(f"Unsupported grid_slot_strategy: {grid_slot_strategy}")
        merged["grid_slot_strategy"] = grid_slot_strategy
    if sheet_reference_images is not None:
        merged["sheet_reference_images"] = sheet_reference_images
    merged = normalize_runtime_config(merged)
    write_json(task_dir(task_id) / "configs" / "runtime_config.json", merged)
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": "user",
            "action": "update_runtime_config",
            "candidate_count": merged["candidate_count"],
            "image_size": merged["image_size"],
            "image_aspect_ratio": merged["image_aspect_ratio"],
            "image_resolution": merged["image_resolution"],
            "image_generation_mode": merged["image_generation_mode"],
            "grid_rows": merged["grid_rows"],
            "grid_cols": merged["grid_cols"],
            "grid_padding": merged["grid_padding"],
            "grid_gap": merged["grid_gap"],
            "grid_cell_count": merged["grid_cell_count"],
            "grid_slot_strategy": merged["grid_slot_strategy"],
            "sheet_reference_image_count": len(merged["sheet_reference_images"]),
        },
    )
    return merged


def _create_item_files(task_id: str, item: dict) -> None:
    root = item_dir(task_id, item["item_id"])
    ensure_dir(root / "artifacts" / "brief_generation")
    ensure_dir(root / "artifacts" / "image_prompt")
    ensure_dir(root / "artifacts" / "image_generation")
    ensure_dir(root / "images")
    write_json(root / "item.json", item)
    write_json(root / "chat.json", [])
    write_json(
        root / "metrics.json",
        {
            "start_time": item["created_at"],
            "end_time": None,
            "iterations": {
                "brief_generation": 0,
                "image_prompt": 0,
                "image_generation": 0,
            },
            "api_calls": 0,
            "token_usage": 0,
            "estimated_cost_usd": 0.0,
            "status": STATUS_DRAFT,
        },
    )


def create_item(
    task_id: str,
    *,
    asset_type: str = "generic_icon",
    title: str = "",
    description: str = "",
    category: str = "",
    extra_context: str = "",
    image_aspect_ratio: str | None = None,
    image_resolution: str | None = None,
    item_id: str | None = None,
) -> dict:
    with _task_operation_lock(task_id):
        task = load_task(task_id)
        now = utc_now()
        existing_ids = task["items"]
        resolved_item_id = item_id or _next_item_id(
            [{"item_id": current_item_id} for current_item_id in existing_ids]
        )
        if resolved_item_id in existing_ids:
            raise ValueError(f"Item already exists: {task_id} {resolved_item_id}")

        item = _normalize_item(
            {
                "asset_type": asset_type,
                "title": title,
                "description": description,
                "category": category,
                "extra_context": extra_context,
                "runtime_overrides": {
                    "image_aspect_ratio": image_aspect_ratio,
                    "image_resolution": image_resolution,
                },
            },
            resolved_item_id,
            now,
        )
        _create_item_files(task_id, item)
        task["items"].append(resolved_item_id)
        task["item_count"] = len(task["items"])
        save_task(task)
    append_item_event(
        task_id,
        resolved_item_id,
        {
            "timestamp": now,
            "source": "system",
            "action": "create_item",
            "to": STATUS_DRAFT,
        },
    )
    append_event(
        task_id,
        {
            "timestamp": now,
            "source": "system",
            "action": "create_item",
            "item_id": resolved_item_id,
            "to": STATUS_DRAFT,
        },
    )
    refresh_task_summary(task_id)
    return load_item(task_id, resolved_item_id)


def update_item(
    task_id: str,
    item_id: str,
    *,
    asset_type: str | None = None,
    title: str | None = None,
    description: str | None = None,
    category: str | None = None,
    extra_context: str | None = None,
    image_aspect_ratio: str | None = None,
    image_resolution: str | None = None,
) -> dict:
    item = load_item(task_id, item_id)
    updated_fields = {
        "asset_type": asset_type if asset_type is not None else item.get("asset_type", "generic_icon"),
        "title": title if title is not None else item.get("title", ""),
        "description": description if description is not None else item.get("description", ""),
        "category": category if category is not None else item.get("category", ""),
        "extra_context": extra_context if extra_context is not None else item.get("extra_context", ""),
    }
    updated_runtime_overrides = deepcopy(item.get("runtime_overrides", default_item_runtime_overrides()))
    if image_aspect_ratio is not None:
        updated_runtime_overrides["image_aspect_ratio"] = image_aspect_ratio or None
    if image_resolution is not None:
        updated_runtime_overrides["image_resolution"] = image_resolution or None
    core_fields = ["asset_type", "title", "description", "category", "extra_context"]
    source_changed = any(item.get(field, "") != updated_fields[field] for field in core_fields)

    item.update(updated_fields)
    item["runtime_overrides"] = updated_runtime_overrides
    if source_changed:
        item["status"] = STATUS_DRAFT
        item["starred_image_versions"] = []
        item["current_versions"] = {
            "brief_generation": None,
            "image_prompt": None,
            "image_generation": None,
        }
        metrics = load_metrics(task_id, item_id)
        metrics["status"] = STATUS_DRAFT
        metrics["end_time"] = None
        save_metrics(task_id, item_id, metrics)
    save_item(task_id, item)
    append_item_event(
        task_id,
        item_id,
        {
            "timestamp": utc_now(),
            "source": "user",
            "action": "update_item",
            "to": item["status"],
            "source_changed": source_changed,
        },
    )
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": "user",
            "action": "update_item",
            "item_id": item_id,
            "to": item["status"],
            "source_changed": source_changed,
        },
    )
    refresh_task_summary(task_id)
    return load_item(task_id, item_id)


def update_item_starred_versions(
    task_id: str,
    item_id: str,
    versions: list[str],
    *,
    source: str = "user",
) -> dict:
    item = load_item(task_id, item_id)
    deduped_versions = list(dict.fromkeys(version for version in versions if version))
    item["starred_image_versions"] = deduped_versions
    save_item(task_id, item)
    append_item_event(
        task_id,
        item_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": "update_starred_image_versions",
            "starred_versions": deduped_versions,
            "count": len(deduped_versions),
        },
    )
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": "update_starred_image_versions",
            "item_id": item_id,
            "starred_versions": deduped_versions,
            "count": len(deduped_versions),
        },
    )
    refresh_task_summary(task_id)
    return load_item(task_id, item_id)


def update_task_settings(
    task_id: str,
    *,
    task_name: str | None = None,
    project_background: str | None = None,
    style_requirements: str | None = None,
    asset_domain: str | None = None,
) -> dict:
    task = load_task(task_id)
    task["task_name"] = task_name if task_name is not None else task.get("task_name", "")
    task["project_background"] = (
        project_background if project_background is not None else task.get("project_background", "")
    )
    task["style_requirements"] = (
        style_requirements if style_requirements is not None else task.get("style_requirements", "")
    )
    task["asset_domain"] = asset_domain if asset_domain is not None else task.get("asset_domain", "game_icon_assets")
    save_task(task)
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": "user",
            "action": "update_task_settings",
            "to": task.get("status", STATUS_DRAFT),
        },
    )
    return load_task(task_id)


def update_task_model_override(
    task_id: str,
    step: str,
    *,
    provider: str | None,
    model: str | None,
) -> dict:
    task = load_task(task_id)
    task["model_overrides"][step] = {"provider": provider, "model": model}
    save_task(task)
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": "user",
            "action": "update_task_model_override",
            "step": step,
            "provider": provider,
            "model": model,
            "to": task.get("status", STATUS_DRAFT),
        },
    )
    return load_task(task_id)


def update_item_model_override(
    task_id: str,
    item_id: str,
    step: str,
    *,
    provider: str | None,
    model: str | None,
) -> dict:
    item = load_item(task_id, item_id)
    item["model_overrides"][step] = {"provider": provider, "model": model}
    save_item(task_id, item)
    append_item_event(
        task_id,
        item_id,
        {
            "timestamp": utc_now(),
            "source": "user",
            "action": "update_item_model_override",
            "step": step,
            "provider": provider,
            "model": model,
            "to": item.get("status", STATUS_DRAFT),
        },
    )
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": "user",
            "action": "update_item_model_override",
            "item_id": item_id,
            "step": step,
            "provider": provider,
            "model": model,
            "to": item.get("status", STATUS_DRAFT),
        },
    )
    return load_item(task_id, item_id)


def load_task(task_id: str) -> dict:
    path = task_dir(task_id) / "task.json"
    if not path.exists():
        raise ValueError(f"Task not found: {task_id}")
    return _ensure_task_schema(read_json(path))  # type: ignore[return-value]


def list_tasks() -> list[dict]:
    ensure_tasks_root()
    tasks = []
    for child in sorted(TASKS_DIR.iterdir()):
        if not child.is_dir():
            continue
        task_path = child / "task.json"
        if not task_path.exists():
            continue
        task = read_json(task_path)
        if not isinstance(task, dict):
            continue
        tasks.append(_ensure_task_schema(task))
    tasks.sort(key=lambda task: task.get("updated_at", ""), reverse=True)
    return tasks


def list_items(task_id: str) -> list[dict]:
    task = load_task(task_id)
    return [load_item(task_id, item_id) for item_id in task["items"]]


def save_task(task: dict) -> None:
    task["updated_at"] = utc_now()
    write_json(task_dir(task["task_id"]) / "task.json", task)


def refresh_task_summary(task_id: str) -> dict:
    task = load_task(task_id)
    items = [load_item(task_id, item_id) for item_id in task["items"]]
    statuses = [item["status"] for item in items]
    if statuses and all(status == "completed" for status in statuses):
        task["status"] = "completed"
    elif any(status != STATUS_DRAFT for status in statuses):
        task["status"] = "in_progress"
    else:
        task["status"] = "draft"
    task["items_summary"] = {
        "draft": sum(1 for status in statuses if status == STATUS_DRAFT),
        "in_progress": sum(1 for status in statuses if status not in {STATUS_DRAFT, "completed"}),
        "completed": sum(1 for status in statuses if status == "completed"),
    }
    save_task(task)
    return task


def load_item(task_id: str, item_id: str) -> dict:
    path = item_dir(task_id, item_id) / "item.json"
    if not path.exists():
        raise ValueError(f"Item not found: {task_id} {item_id}")
    item = _ensure_item_schema(read_json(path))  # type: ignore[assignment]
    item = reconcile_item_generating_state(task_id, item_id, item)
    return item  # type: ignore[return-value]


def save_item(task_id: str, item: dict) -> None:
    item["updated_at"] = utc_now()
    write_json(item_dir(task_id, item["item_id"]) / "item.json", item)


def load_metrics(task_id: str, item_id: str) -> dict:
    return read_json(item_dir(task_id, item_id) / "metrics.json")  # type: ignore[return-value]


def save_metrics(task_id: str, item_id: str, metrics: dict) -> None:
    write_json(item_dir(task_id, item_id) / "metrics.json", metrics)


def append_event(task_id: str, payload: dict) -> None:
    append_jsonl(task_dir(task_id) / "events.jsonl", payload)


def append_item_event(task_id: str, item_id: str, payload: dict) -> None:
    append_jsonl(item_dir(task_id, item_id) / "events.jsonl", payload)


def load_task_events(task_id: str) -> list[dict]:
    return read_jsonl(task_dir(task_id) / "events.jsonl")


def load_item_events(task_id: str, item_id: str) -> list[dict]:
    return read_jsonl(item_dir(task_id, item_id) / "events.jsonl")


def load_item_chat(task_id: str, item_id: str) -> list[dict]:
    path = item_dir(task_id, item_id) / "chat.json"
    if not path.exists():
        return []
    payload = read_json(path)
    if isinstance(payload, list):
        return payload
    return []


def append_item_chat(task_id: str, item_id: str, payload: dict) -> list[dict]:
    history = load_item_chat(task_id, item_id)
    history.append(payload)
    write_json(item_dir(task_id, item_id) / "chat.json", history)
    return history


def load_style_spec(task_id: str) -> dict:
    return read_json(task_dir(task_id) / "configs" / "style_spec.json")  # type: ignore[return-value]


def load_runtime_config(task_id: str) -> dict:
    payload = read_json(task_dir(task_id) / "configs" / "runtime_config.json")  # type: ignore[assignment]
    return normalize_runtime_config(payload)


def artifact_dir(task_id: str, item_id: str, step: str) -> Path:
    return item_dir(task_id, item_id) / "artifacts" / step


def artifact_path(
    task_id: str,
    item_id: str,
    step: str,
    version: str,
    *,
    manual: bool = False,
) -> Path:
    suffix = "_manual" if manual else ""
    return artifact_dir(task_id, item_id, step) / f"{version}{suffix}.json"


def next_version(task_id: str, item_id: str, step: str) -> str:
    root = artifact_dir(task_id, item_id, step)
    ensure_dir(root)
    max_id = 0
    for child in root.glob("v*.json"):
        match = re.match(r"^v(\d+)", child.stem)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return f"v{max_id + 1:03d}"


def write_artifact(
    task_id: str,
    item_id: str,
    step: str,
    payload: dict,
    *,
    version: str | None = None,
    manual: bool = False,
) -> str:
    resolved_version = version or next_version(task_id, item_id, step)
    serialized = deepcopy(payload)
    serialized["version"] = resolved_version
    write_json(
        artifact_path(task_id, item_id, step, resolved_version, manual=manual),
        serialized,
    )
    return resolved_version


def load_artifact(task_id: str, item_id: str, step: str, version: str) -> dict:
    preferred = artifact_path(task_id, item_id, step, version)
    manual = artifact_path(task_id, item_id, step, version, manual=True)
    if preferred.exists():
        return read_json(preferred)  # type: ignore[return-value]
    if manual.exists():
        return read_json(manual)  # type: ignore[return-value]
    raise ValueError(f"Artifact not found: {task_id} {item_id} {step} {version}")


def list_artifacts(task_id: str, item_id: str, step: str) -> list[dict]:
    root = artifact_dir(task_id, item_id, step)
    if not root.exists():
        return []

    artifacts = []
    for path in sorted(root.glob("v*.json")):
        payload = read_json(path)
        artifacts.append(
            {
                "version": payload["version"],
                "step": step,
                "manual": path.stem.endswith("_manual"),
                "path": str(path),
                "created_at": payload.get("created_at"),
                "_payload": payload,
            }
        )

    artifacts.sort(key=lambda artifact: (artifact["version"], artifact["manual"]))
    return artifacts


def summarize_item_images(task_id: str, item_id: str) -> dict:
    item = load_item(task_id, item_id)
    approved_image_path = None
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = item_dir(task_id, item_id) / "images" / f"approved{suffix}"
        if candidate.exists():
            approved_image_path = candidate
            break

    current_version = item.get("current_versions", {}).get("image_generation")
    preview_image_path = approved_image_path
    pending_image_jobs = 0

    if not preview_image_path and current_version:
        try:
            current_artifact = load_artifact(task_id, item_id, STEP_IMAGE_GENERATION, current_version)
            candidates = (current_artifact.get("output") or {}).get("candidates", [])
            for candidate in candidates:
                image_path = candidate.get("image_path")
                if image_path:
                    resolved = item_dir(task_id, item_id) / "images" / image_path
                    if resolved.exists():
                        preview_image_path = resolved
                        break
        except ValueError:
            pass

    for artifact_meta in reversed(list_artifacts(task_id, item_id, STEP_IMAGE_GENERATION)):
        artifact = artifact_meta.get("_payload")
        if not isinstance(artifact, dict):
            artifact = load_artifact(task_id, item_id, STEP_IMAGE_GENERATION, artifact_meta["version"])
        async_status = str((artifact.get("async_job") or {}).get("status", "")).lower()
        if async_status in PENDING_ASYNC_STATUSES:
            pending_image_jobs += 1

        if preview_image_path:
            continue

        candidates = (artifact.get("output") or {}).get("candidates", [])
        for candidate in candidates:
            image_path = candidate.get("image_path")
            if not image_path:
                continue
            resolved = item_dir(task_id, item_id) / "images" / image_path
            if resolved.exists():
                preview_image_path = resolved
                break

    return {
        "preview_image_path": preview_image_path,
        "pending_image_jobs": pending_image_jobs,
    }


def compute_batch_metrics(task_id: str) -> dict:
    task = load_task(task_id)
    item_ids = list(task.get("items", []))
    total_elapsed_seconds = _elapsed_seconds(task.get("created_at"), task.get("updated_at")) or 0.0
    item_elapsed_seconds: list[float] = []
    redo_counts = {
        STEP_BRIEF_GENERATION: 0,
        STEP_IMAGE_PROMPT: 0,
        STEP_IMAGE_GENERATION: 0,
    }
    failure_counts = {
        STEP_BRIEF_GENERATION: 0,
        STEP_IMAGE_PROMPT: 0,
        STEP_IMAGE_GENERATION: 0,
        "stale": 0,
    }
    starred_images = 0
    items_with_starred = 0
    adopted_from_starred = 0
    active_background_jobs = 0
    generated_items = 0
    first_image_started_seconds: float | None = None
    image_model_counts: dict[str, int] = {}
    stuck_items: list[dict] = []
    failed_items: list[dict] = []
    last_error_by_item: dict[str, str] = {}
    active_provider_requests: list[dict] = []

    for item_id in item_ids:
        item = load_item(task_id, item_id)
        metrics = load_metrics(task_id, item_id)
        events = load_item_events(task_id, item_id)

        elapsed = _elapsed_seconds(metrics.get("start_time"), metrics.get("end_time"))
        if elapsed is not None:
            item_elapsed_seconds.append(elapsed)

        iterations = metrics.get("iterations", {})
        for step in (STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT, STEP_IMAGE_GENERATION):
            count = int(iterations.get(step, 0) or 0)
            redo_counts[step] += max(0, count - 1)

        for event in events:
            action = str(event.get("action", ""))
            step = str(event.get("step", ""))
            if action.startswith("fail_") and step in failure_counts:
                failure_counts[step] += 1
            elif action == "recover_stale_generation":
                failure_counts["stale"] += 1

        starred_versions = list(item.get("starred_image_versions", []))
        starred_images += len(starred_versions)
        if starred_versions:
            items_with_starred += 1
        current_image_version = item.get("current_versions", {}).get(STEP_IMAGE_GENERATION)
        if current_image_version and current_image_version in starred_versions:
            adopted_from_starred += 1

        image_summary = summarize_item_images(task_id, item_id)
        active_background_jobs += int(image_summary.get("pending_image_jobs", 0))
        if item.get("status") in {STATUS_IMAGE_GENERATED, STATUS_COMPLETED}:
            generated_items += 1
        updated_at = _parse_utc_timestamp(item.get("updated_at"))
        is_stale_generating = (
            item.get("status") == STATUS_IMAGE_GENERATING
            and updated_at is not None
            and (datetime.now(timezone.utc) - updated_at).total_seconds() >= GENERATING_STALE_SECONDS
            and int(image_summary.get("pending_image_jobs", 0)) == 0
        )
        if is_stale_generating:
            stuck_items.append(
                {
                    "item_id": item_id,
                    "title": item.get("title", ""),
                    "status": item.get("status"),
                    "updated_at": item.get("updated_at"),
                }
            )
        if item.get("status") == STATUS_FAILED:
            failed_items.append(
                {
                    "item_id": item_id,
                    "title": item.get("title", ""),
                    "status": item.get("status"),
                    "updated_at": item.get("updated_at"),
                }
            )

        for event in reversed(events):
            action = str(event.get("action", ""))
            if action.startswith("fail_") or action == "recover_stale_generation":
                last_error_by_item[item_id] = str(event.get("error") or event.get("reason") or action)
                break

        for artifact_meta in list_artifacts(task_id, item_id, STEP_IMAGE_GENERATION):
            artifact = artifact_meta.get("_payload")
            if not isinstance(artifact, dict):
                artifact = load_artifact(task_id, item_id, STEP_IMAGE_GENERATION, artifact_meta["version"])

            created_at = artifact.get("created_at")
            if created_at:
                started_seconds = _elapsed_seconds(task.get("created_at"), created_at)
                if started_seconds is not None and (
                    first_image_started_seconds is None or started_seconds < first_image_started_seconds
                ):
                    first_image_started_seconds = started_seconds

            model_id = str(artifact.get("model") or "").strip()
            if model_id:
                image_model_counts[model_id] = image_model_counts.get(model_id, 0) + 1

            async_job = artifact.get("async_job") or {}
            async_status = str(async_job.get("status", "")).lower()
            if async_status in PENDING_ASYNC_STATUSES:
                active_provider_requests.append(
                    {
                        "item_id": item_id,
                        "title": item.get("title", ""),
                        "version": artifact.get("version"),
                        "provider": artifact.get("provider"),
                        "model": artifact.get("model"),
                        "task_id": async_job.get("task_id"),
                        "status": async_job.get("status"),
                        "updated_at": async_job.get("updated_at"),
                    }
                )

    avg_item_elapsed_seconds = (
        sum(item_elapsed_seconds) / len(item_elapsed_seconds) if item_elapsed_seconds else None
    )
    top_image_models = [
        {"model": model, "count": count}
        for model, count in sorted(image_model_counts.items(), key=lambda row: (-row[1], row[0]))[:3]
    ]

    return {
        "total_elapsed_seconds": total_elapsed_seconds,
        "avg_item_elapsed_seconds": avg_item_elapsed_seconds,
        "generated_items": generated_items,
        "active_background_jobs": active_background_jobs,
        "first_image_started_seconds": first_image_started_seconds,
        "redo_counts": redo_counts,
        "total_redos": sum(redo_counts.values()),
        "starred_images": starred_images,
        "items_with_starred": items_with_starred,
        "adopted_from_starred": adopted_from_starred,
        "failure_counts": failure_counts,
        "top_image_models": top_image_models,
        "stuck_items": stuck_items,
        "failed_items": failed_items,
        "last_error_by_item": last_error_by_item,
        "active_provider_requests": active_provider_requests,
    }


def export_starred_images_zip(task_id: str) -> Path:
    task = load_task(task_id)
    items = list_items(task_id)
    export_root = task_dir(task_id) / "exports"
    ensure_dir(export_root)
    archive_path = export_root / "starred-images.zip"

    manifest: dict[str, object] = {
        "task_id": task_id,
        "task_name": task.get("task_name", task_id),
        "exported_at": utc_now(),
        "items": [],
    }
    flat_rows: list[dict[str, str]] = []
    exported_count = 0

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in items:
            starred_versions = list(item.get("starred_image_versions", []))
            if not starred_versions:
                continue

            item_name = _safe_path_fragment(item.get("title") or item["item_id"])
            item_folder = f"{item['item_id']}_{item_name}"
            item_manifest: dict[str, object] = {
                "item_id": item["item_id"],
                "title": item.get("title", ""),
                "starred_versions": [],
            }

            for version in starred_versions:
                try:
                    artifact = load_artifact(task_id, item["item_id"], STEP_IMAGE_GENERATION, version)
                except ValueError:
                    continue

                candidates = (artifact.get("output") or {}).get("candidates", [])
                exported_files: list[str] = []
                for index, candidate in enumerate(candidates, start=1):
                    image_path = candidate.get("image_path")
                    if not image_path:
                        continue
                    source_path = item_dir(task_id, item["item_id"]) / "images" / image_path
                    if not source_path.exists():
                        continue
                    suffix = source_path.suffix or Path(str(image_path)).suffix or ".png"
                    candidate_id = candidate.get("candidate_id") or f"candidate_{index:02d}"
                    safe_candidate_id = _safe_path_fragment(str(candidate_id))
                    file_name = (
                        f"{item['item_id']}_{item_name}_{version}_{safe_candidate_id}{suffix}"
                    )
                    archive_name = f"{item_folder}/{file_name}"
                    flat_archive_name = f"flat/{file_name}"
                    archive.write(source_path, arcname=archive_name)
                    archive.write(source_path, arcname=flat_archive_name)
                    exported_files.append(archive_name)
                    flat_rows.append(
                        {
                            "item_id": item["item_id"],
                            "title": item.get("title", ""),
                            "version": version,
                            "provider": str(artifact.get("provider") or ""),
                            "model": str(artifact.get("model") or ""),
                            "candidate_id": str(candidate_id),
                            "grouped_path": archive_name,
                            "flat_path": flat_archive_name,
                        }
                    )
                    exported_count += 1

                if exported_files:
                    item_manifest["starred_versions"].append(
                        {
                            "version": version,
                            "provider": artifact.get("provider"),
                            "model": artifact.get("model"),
                            "created_at": artifact.get("created_at"),
                            "files": exported_files,
                        }
                    )

            if item_manifest["starred_versions"]:
                manifest["items"].append(item_manifest)

        if exported_count == 0:
            raise ValueError("当前批次还没有星标图可导出")

        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
        csv_buffer = StringIO()
        writer = csv.DictWriter(
            csv_buffer,
            fieldnames=[
                "item_id",
                "title",
                "version",
                "provider",
                "model",
                "candidate_id",
                "grouped_path",
                "flat_path",
            ],
        )
        writer.writeheader()
        writer.writerows(flat_rows)
        archive.writestr("manifest.csv", csv_buffer.getvalue())

    return archive_path
