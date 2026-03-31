from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import re
import shutil

from .config import (
    DEFAULT_RUNTIME_CONFIG,
    DEFAULT_STYLE_SPEC,
    STATUS_DRAFT,
    STEP_BRIEF_GENERATION,
    STEP_IMAGE_GENERATION,
    STEP_IMAGE_PROMPT,
    TASKS_DIR,
)
from .utils import ensure_dir, utc_now


TASK_ID_PATTERN = re.compile(r"^task_(\d+)$")
ITEM_ID_PATTERN = re.compile(r"^item_(\d+)$")


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


def normalize_runtime_config(runtime_config: dict | None) -> dict:
    merged = deepcopy(DEFAULT_RUNTIME_CONFIG)
    if isinstance(runtime_config, dict):
        merged.update(runtime_config)
    # 产品语义调整：候选图按“每次生成 1 张、历史累积”工作，不再一次批量吐多张。
    merged["candidate_count"] = 1
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
        "current_versions": {
            "brief_generation": None,
            "image_prompt": None,
            "image_generation": None,
        },
        "model_overrides": deepcopy(raw_item.get("model_overrides", default_model_overrides())),
        "runtime_overrides": deepcopy(raw_item.get("runtime_overrides", default_item_runtime_overrides())),
    }


def _ensure_task_schema(task: dict) -> dict:
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
    return item


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
    root = task_dir(task_id)
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
) -> dict:
    current = load_runtime_config(task_id)
    merged = normalize_runtime_config(current)
    if image_size is not None:
        merged["image_size"] = image_size
    if image_aspect_ratio is not None:
        merged["image_aspect_ratio"] = image_aspect_ratio
    if image_resolution is not None:
        merged["image_resolution"] = image_resolution
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
        if not isinstance(task, dict) or "items" not in task:
            continue
        tasks.append(task)
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
    return _ensure_item_schema(read_json(path))  # type: ignore[return-value]


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
            }
        )

    artifacts.sort(key=lambda artifact: (artifact["version"], artifact["manual"]))
    return artifacts
