from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import re

from .config import (
    DEFAULT_RUNTIME_CONFIG,
    DEFAULT_STYLE_SPEC,
    STATUS_DRAFT,
    TASKS_DIR,
)
from .utils import ensure_dir, utc_now


TASK_ID_PATTERN = re.compile(r"^task_(\d+)$")
ITEM_ID_PATTERN = re.compile(r"^item_(\d+)$")


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
    }


def create_task(
    *,
    task_name: str,
    project_context: str,
    items: list[dict],
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
    if not items:
        raise ValueError("A task must include at least one item")

    ensure_dir(root / "configs")
    ensure_dir(root / "items")
    ensure_dir(root / "exports")

    now = utc_now()
    normalized_items = []
    for raw_item in items:
        item_id = raw_item.get("item_id") or _next_item_id(normalized_items)
        item = _normalize_item(raw_item, item_id, now)
        normalized_items.append(item)
        _create_item_files(resolved_task_id, item)

    task = {
        "task_id": resolved_task_id,
        "task_name": task_name,
        "project_context": project_context,
        "asset_domain": asset_domain,
        "created_at": now,
        "updated_at": now,
        "status": "draft",
        "items": [item["item_id"] for item in normalized_items],
        "item_count": len(normalized_items),
        "style_spec_ref": "configs/style_spec.json",
        "runtime_config_ref": "configs/runtime_config.json",
    }

    write_json(root / "task.json", task)
    write_json(root / "configs" / "style_spec.json", deepcopy(style_spec or DEFAULT_STYLE_SPEC))
    write_json(
        root / "configs" / "runtime_config.json",
        deepcopy(runtime_config or DEFAULT_RUNTIME_CONFIG),
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


def load_task(task_id: str) -> dict:
    path = task_dir(task_id) / "task.json"
    if not path.exists():
        raise ValueError(f"Task not found: {task_id}")
    return read_json(path)  # type: ignore[return-value]


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
    return read_json(path)  # type: ignore[return-value]


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


def load_style_spec(task_id: str) -> dict:
    return read_json(task_dir(task_id) / "configs" / "style_spec.json")  # type: ignore[return-value]


def load_runtime_config(task_id: str) -> dict:
    return read_json(task_dir(task_id) / "configs" / "runtime_config.json")  # type: ignore[return-value]


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
