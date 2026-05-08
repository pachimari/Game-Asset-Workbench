from __future__ import annotations

from pathlib import Path
import re
import shutil

from PIL import Image

from .config import (
    STATUS_BRIEF_GENERATED,
    STATUS_DRAFT,
    STATUS_FAILED,
    STATUS_IMAGE_GENERATED,
    STEP_BRIEF_GENERATION,
    STEP_IMAGE_GENERATION,
)
from .pipeline import approve_step, run_step
from .provider_runtime import generate_brief_output
from .providers.registry import get_async_image_provider
from .settings import DEFAULT_PROMPT_TEMPLATES, load_global_settings, provider_settings_for, resolve_stage_selection
from .storage import (
    PENDING_ASYNC_STATUSES,
    append_event,
    append_item_event,
    create_item,
    item_dir,
    list_items,
    load_artifact,
    load_item,
    load_metrics,
    load_runtime_config,
    load_task,
    read_json,
    refresh_task_summary,
    save_item,
    save_metrics,
    task_dir,
    write_artifact,
    write_json,
)
from .utils import ensure_dir, utc_now


SHEET_ID_PATTERN = re.compile(r"^sheet_v(\d+)$")
TILE_REVIEW_STATUSES = {"pending", "selected", "rejected", "emergent"}
DEFAULT_GRID_SHEET_TEMPLATE = DEFAULT_PROMPT_TEMPLATES["grid_sheet_prompt_template"]
DEFAULT_GRID_SHEET_NEGATIVE_PROMPT = DEFAULT_PROMPT_TEMPLATES["grid_sheet_negative_prompt"]


def sheets_dir(task_id: str) -> Path:
    return task_dir(task_id) / "sheets"


def sheet_dir(task_id: str, sheet_id: str) -> Path:
    return sheets_dir(task_id) / sheet_id


def sheet_path(task_id: str, sheet_id: str) -> Path:
    return sheet_dir(task_id, sheet_id) / "sheet.json"


def next_sheet_id(task_id: str) -> str:
    root = sheets_dir(task_id)
    ensure_dir(root)
    max_id = 0
    for child in root.iterdir():
        if not child.is_dir():
            continue
        match = SHEET_ID_PATTERN.match(child.name)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return f"sheet_v{max_id + 1:03d}"


def load_sheet(task_id: str, sheet_id: str) -> dict:
    path = sheet_path(task_id, sheet_id)
    if not path.exists():
        raise ValueError(f"Sheet not found: {task_id} {sheet_id}")
    return read_json(path)  # type: ignore[return-value]


def save_sheet(task_id: str, sheet: dict) -> dict:
    sheet["updated_at"] = utc_now()
    write_json(sheet_path(task_id, sheet["sheet_id"]), sheet)
    return sheet


def list_sheets(task_id: str) -> list[dict]:
    root = sheets_dir(task_id)
    if not root.exists():
        return []
    rows: list[dict] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "sheet.json").exists():
            rows.append(read_json(child / "sheet.json"))  # type: ignore[arg-type]
    rows.sort(key=lambda row: str(row.get("sheet_id", "")), reverse=True)
    return rows


def _brief_for_item(task_id: str, item: dict) -> dict:
    brief_version = item.get("current_versions", {}).get(STEP_BRIEF_GENERATION)
    if brief_version:
        try:
            artifact = load_artifact(task_id, item["item_id"], STEP_BRIEF_GENERATION, brief_version)
            output = artifact.get("output") or {}
            return {
                "source": "brief",
                "title": output.get("title") or item.get("title", ""),
                "description": output.get("description") or item.get("description", ""),
                "icon_subject": output.get("icon_subject") or item.get("title", ""),
                "visual_focus": output.get("visual_focus") or "",
                "keywords": output.get("keywords") if isinstance(output.get("keywords"), list) else [],
            }
        except ValueError:
            pass
    return {
        "source": "raw_item",
        "title": item.get("title", ""),
        "description": item.get("description", ""),
        "icon_subject": item.get("title", "") or item.get("description", ""),
        "visual_focus": item.get("extra_context", ""),
        "keywords": [value for value in [item.get("asset_type"), item.get("category")] if value],
    }


def _ensure_grid_sheet_briefs(task_id: str, items: list[dict], *, source: str) -> dict:
    results = []
    for item in items:
        item_id = item["item_id"]
        current = load_item(task_id, item_id)
        if current.get("current_versions", {}).get(STEP_BRIEF_GENERATION):
            results.append({"item_id": item_id, "status": "exists"})
            continue

        if current.get("status") not in {STATUS_DRAFT, STATUS_BRIEF_GENERATED, STATUS_FAILED}:
            version = _write_grid_sheet_brief_without_status_reset(task_id, item_id, source=source)
            results.append({"item_id": item_id, "status": "sidecar_generated", "version": version})
            continue

        if current.get("status") != STATUS_BRIEF_GENERATED:
            run_step(task_id, item_id, STEP_BRIEF_GENERATION, source=source)
        current = load_item(task_id, item_id)
        if current.get("status") == STATUS_BRIEF_GENERATED:
            approve_step(task_id, item_id, STEP_BRIEF_GENERATION, source=source)
        results.append({"item_id": item_id, "status": "generated"})

    return {
        "required": len(items),
        "generated": sum(1 for row in results if row["status"] == "generated"),
        "sidecar_generated": sum(1 for row in results if row["status"] == "sidecar_generated"),
        "existing": sum(1 for row in results if row["status"] == "exists"),
        "items": results,
    }


def _write_grid_sheet_brief_without_status_reset(task_id: str, item_id: str, *, source: str) -> str:
    task = load_task(task_id)
    item = load_item(task_id, item_id)
    global_settings = load_global_settings()
    selected_runtime = resolve_stage_selection(task, item, global_settings, STEP_BRIEF_GENERATION)
    provider_id = selected_runtime["provider"]
    model_id = selected_runtime["model"]
    provider_settings = provider_settings_for(global_settings, provider_id)
    prompt_templates = global_settings.get("prompt_templates", {})
    output = generate_brief_output(
        provider_id=provider_id,
        provider_config=provider_settings,
        api_key=provider_settings.get("api_key", ""),
        model=model_id,
        asset_type=item["asset_type"],
        title=item.get("title", ""),
        description=item["description"],
        category=item.get("category", ""),
        project_background=task.get("project_background", task.get("project_context", "")),
        style_requirements=task.get("style_requirements", ""),
        extra_context=item.get("extra_context", ""),
        system_prompt=prompt_templates.get("brief_system_prompt"),
    )
    payload = {
        "step": STEP_BRIEF_GENERATION,
        "provider": provider_id,
        "model": model_id,
        "created_at": utc_now(),
        "input": {
            "asset_type": item["asset_type"],
            "title": item.get("title", ""),
            "description": item["description"],
            "category": item.get("category", ""),
            "project_background": task.get("project_background", task.get("project_context", "")),
            "style_requirements": task.get("style_requirements", ""),
            "extra_context": item.get("extra_context", ""),
            "selected_runtime": selected_runtime,
            "purpose": "grid_sheet_planning",
        },
        "output": output,
    }
    version = write_artifact(task_id, item_id, STEP_BRIEF_GENERATION, payload)
    item = load_item(task_id, item_id)
    item["current_versions"][STEP_BRIEF_GENERATION] = version
    save_item(task_id, item)
    append_item_event(
        task_id,
        item_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": "grid_sheet_brief_without_status_reset",
            "version": version,
            "status_preserved": item.get("status"),
        },
    )
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": "grid_sheet_brief_without_status_reset",
            "item_id": item_id,
            "version": version,
            "status_preserved": item.get("status"),
        },
    )
    return version


def _emergent_brief(*, index: int, task: dict) -> dict:
    return {
        "source": "emergent_slot",
        "title": f"涌现槽 {index:02d}",
        "description": (
            "自由涌现一个同批次世界观和统一风格下的原创游戏资产图标。"
            "不要重复已指定槽位的主题，优先补充新的攻击、防御、治疗、控制、位移、召唤、诅咒或资源类视觉概念。"
        ),
        "icon_subject": "原创涌现游戏资产图标",
        "visual_focus": (
            "探索槽位：让模型自由发明，但必须保持单主体、图标可读、居中、安全边距充足、无文字。"
        ),
        "keywords": ["grid_sheet", "emergent", task.get("asset_domain", "game_icon_assets")],
    }


def _render_grid_sheet_template(template: str, values: dict[str, object]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return rendered


def _build_grid_sheet_prompt(*, task: dict, runtime: dict, slots: list[dict]) -> dict:
    rows = int(runtime.get("grid_rows", 8))
    cols = int(runtime.get("grid_cols", 8))
    slot_lines = []
    slot_briefs = []
    for slot in slots:
        brief = slot["brief"]
        slot_briefs.append(
            {
                "cell_id": slot["cell_id"],
                "kind": slot.get("kind", "bound"),
                "item_id": slot.get("item_id"),
                "title": brief["title"],
                "source": brief["source"],
                "icon_subject": brief["icon_subject"],
                "visual_focus": brief["visual_focus"],
                "description": brief["description"],
                "keywords": brief["keywords"],
            }
        )
        fragments = [
            f"{slot['cell_id']}: {brief['title']}",
            f"subject={brief['icon_subject']}",
            f"focus={brief['visual_focus']}",
            f"description={brief['description']}",
        ]
        if brief["keywords"]:
            fragments.append("keywords=" + ", ".join(str(value) for value in brief["keywords"]))
        slot_lines.append(" | ".join(fragment for fragment in fragments if fragment and not fragment.endswith("=")))

    prompt_templates = load_global_settings().get("prompt_templates", {})
    template = prompt_templates.get("grid_sheet_prompt_template", "")
    if not template:
        template = DEFAULT_GRID_SHEET_TEMPLATE
    prompt = _render_grid_sheet_template(
        template,
        {
            "rows": rows,
            "cols": cols,
            "cell_count": rows * cols,
            "project_background": task.get("project_background", ""),
            "style_requirements": task.get("style_requirements", ""),
            "slot_lines": "\n".join(slot_lines),
        },
    )
    negative_prompt = prompt_templates.get("grid_sheet_negative_prompt", "")
    if not negative_prompt:
        negative_prompt = DEFAULT_GRID_SHEET_NEGATIVE_PROMPT
    return {
        "mode": "grid_sheet",
        "brief_strategy": "slot briefs use approved item brief when available, otherwise raw item input",
        "template": "grid_sheet_prompt_template",
        "slot_briefs": slot_briefs,
        "prompt": prompt.strip(),
        "negative_prompt": negative_prompt,
        "constraints": {
            "rows": rows,
            "cols": cols,
            "order": "row_major",
            "text_allowed": False,
            "one_subject_per_cell": True,
            "no_cross_cell_subjects": True,
        },
    }


def plan_grid_sheet(task_id: str, *, source: str = "cli") -> dict:
    task = load_task(task_id)
    runtime = load_runtime_config(task_id)
    if runtime.get("image_generation_mode") != "grid_sheet":
        raise ValueError("当前批次不是 grid_sheet 出图模式")

    rows = int(runtime.get("grid_rows", 8))
    cols = int(runtime.get("grid_cols", 8))
    capacity = rows * cols
    items = list_items(task_id)
    if not items:
        raise ValueError("当前批次没有可规划的 item")

    selected_items = items[:capacity]
    brief_summary = _ensure_grid_sheet_briefs(task_id, selected_items, source=source)
    selected_items = [load_item(task_id, item["item_id"]) for item in selected_items]
    sheet_id = next_sheet_id(task_id)
    root = sheet_dir(task_id, sheet_id)
    ensure_dir(root / "images" / "tiles")

    slots = []
    for index, item in enumerate(selected_items):
        row = index // cols + 1
        col = index % cols + 1
        cell_id = f"r{row:02d}c{col:02d}"
        brief = _brief_for_item(task_id, item)
        slots.append(
            {
                "cell_id": cell_id,
                "row": row,
                "col": col,
                "kind": "bound",
                "item_id": item["item_id"],
                "title": item.get("title", ""),
                "brief": brief,
            }
        )
    for offset in range(len(selected_items), capacity):
        row = offset // cols + 1
        col = offset % cols + 1
        cell_id = f"r{row:02d}c{col:02d}"
        emergent_index = offset - len(selected_items) + 1
        slots.append(
            {
                "cell_id": cell_id,
                "row": row,
                "col": col,
                "kind": "emergent",
                "item_id": None,
                "title": f"涌现槽 {emergent_index:02d}",
                "brief": _emergent_brief(index=emergent_index, task=task),
            }
        )

    prompt = _build_grid_sheet_prompt(task=task, runtime=runtime, slots=slots)
    now = utc_now()
    sheet = {
        "sheet_id": sheet_id,
        "status": "planned",
        "created_at": now,
        "updated_at": now,
        "input": {
            "rows": rows,
            "cols": cols,
            "grid_padding": runtime.get("grid_padding", 0),
            "grid_gap": runtime.get("grid_gap", 0),
            "image_aspect_ratio": runtime.get("image_aspect_ratio", "1:1"),
            "image_resolution": runtime.get("image_resolution", "1K"),
            "item_count": len(selected_items),
            "emergent_item_count": max(0, capacity - len(selected_items)),
            "remaining_item_count": max(0, len(items) - len(selected_items)),
        },
        "brief_generation": brief_summary,
        "prompt": prompt,
        "slots": slots,
        "tiles": [],
    }
    save_sheet(task_id, sheet)
    append_event(
        task_id,
        {
            "timestamp": now,
            "source": source,
            "action": "plan_grid_sheet",
            "sheet_id": sheet_id,
            "item_count": len(selected_items),
            "remaining_item_count": max(0, len(items) - len(selected_items)),
        },
    )
    return sheet


def submit_grid_sheet_generation(task_id: str, sheet_id: str, *, source: str = "cli") -> dict:
    task = load_task(task_id)
    runtime = load_runtime_config(task_id)
    sheet = load_sheet(task_id, sheet_id)
    global_settings = load_global_settings()
    selected_runtime = resolve_stage_selection(
        task,
        {"model_overrides": {}, "runtime_overrides": {}},
        global_settings,
        STEP_IMAGE_GENERATION,
    )
    provider_id = selected_runtime["provider"]
    model_id = selected_runtime["model"]
    provider_settings = provider_settings_for(global_settings, provider_id)
    if provider_settings.get("provider_type") != "async_image":
        raise ValueError("grid_sheet 生成第一版仅支持 async_image provider")
    api_key = provider_settings.get("api_key", "")
    provider = get_async_image_provider(provider_id, provider_settings)
    prompt = sheet.get("prompt", {}).get("prompt", "")
    negative_prompt = sheet.get("prompt", {}).get("negative_prompt", "")
    if negative_prompt:
        prompt = f"{prompt}\nAvoid: {negative_prompt}"
    response = provider.submit_generation(
        api_key=api_key,
        model=model_id,
        prompt=prompt,
        aspect_ratio=runtime.get("image_aspect_ratio", "1:1"),
        resolution=runtime.get("image_resolution", "1K"),
    )
    sheet["status"] = "generating"
    sheet["provider"] = provider_id
    sheet["model"] = model_id
    sheet["async_job"] = {
        "provider_type": provider_settings.get("provider_type"),
        "status": response.get("status", "queued"),
        "task_id": response.get("id"),
        "progress": response.get("progress", 0),
        "submitted_at": utc_now(),
    }
    sheet["selected_runtime"] = selected_runtime
    save_sheet(task_id, sheet)
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": "submit_grid_sheet_generation",
            "sheet_id": sheet_id,
            "provider": provider_id,
            "model": model_id,
            "remote_task_id": response.get("id"),
        },
    )
    return sheet


def poll_grid_sheet_generation(task_id: str, sheet_id: str, *, source: str = "cli") -> dict:
    sheet = load_sheet(task_id, sheet_id)
    async_job = sheet.get("async_job") or {}
    remote_task_id = async_job.get("task_id")
    if not remote_task_id:
        raise ValueError("当前 sheet 不是异步生成任务")
    global_settings = load_global_settings()
    provider_id = sheet.get("provider")
    provider_settings = provider_settings_for(global_settings, provider_id)
    provider = get_async_image_provider(provider_id, provider_settings)
    response = provider.poll_generation(
        api_key=provider_settings.get("api_key", ""),
        task_id=remote_task_id,
    )
    remote_status = str(response.get("status", "")).lower()
    async_job["status"] = remote_status or async_job.get("status", "queued")
    async_job["progress"] = response.get("progress", async_job.get("progress", 0))
    async_job["updated_at"] = utc_now()
    sheet["async_job"] = async_job

    if remote_status in PENDING_ASYNC_STATUSES:
        sheet["status"] = "generating"
        save_sheet(task_id, sheet)
        return sheet

    if remote_status == "completed":
        urls = []
        result = response.get("result", {})
        if isinstance(result, dict):
            for row in result.get("data", []):
                if isinstance(row, dict) and row.get("url"):
                    urls.append(row["url"])
        if not urls:
            raise ValueError("grid sheet 任务已完成，但没有返回结果图 URL")
        image_root = sheet_dir(task_id, sheet_id) / "images"
        ensure_dir(image_root)
        source_path = image_root / "source.png"
        provider.download_result(url=urls[0], destination=source_path)
        sheet["status"] = "generated"
        sheet["source_image_path"] = "images/source.png"
        sheet["source_url"] = urls[0]
        save_sheet(task_id, sheet)
        append_event(
            task_id,
            {
                "timestamp": utc_now(),
                "source": source,
                "action": "complete_grid_sheet_generation",
                "sheet_id": sheet_id,
                "remote_status": remote_status,
            },
        )
        return sheet

    if remote_status in {"failed", "cancelled", "canceled"}:
        sheet["status"] = "failed"
        async_job["error"] = str(response.get("error", response))
        save_sheet(task_id, sheet)
        raise ValueError(str(response.get("error", remote_status)))

    save_sheet(task_id, sheet)
    return sheet


def split_grid_sheet(task_id: str, sheet_id: str, *, source: str = "cli") -> dict:
    sheet = load_sheet(task_id, sheet_id)
    source_image_path = sheet.get("source_image_path")
    if not source_image_path:
        raise ValueError("当前 sheet 没有 source image，无法切图")
    source_path = sheet_dir(task_id, sheet_id) / source_image_path
    if not source_path.exists():
        raise ValueError(f"Sheet source image not found: {source_image_path}")

    config = sheet.get("input", {})
    rows = int(config.get("rows", 8))
    cols = int(config.get("cols", 8))
    padding = int(config.get("grid_padding", 0) or 0)
    gap = int(config.get("grid_gap", 0) or 0)
    tile_root = sheet_dir(task_id, sheet_id) / "images" / "tiles"
    ensure_dir(tile_root)

    existing_tiles = {tile.get("cell_id"): tile for tile in sheet.get("tiles", [])}
    tiles = []
    with Image.open(source_path) as image:
        width, height = image.size
        usable_width = width - padding * 2 - gap * (cols - 1)
        usable_height = height - padding * 2 - gap * (rows - 1)
        if usable_width <= 0 or usable_height <= 0:
            raise ValueError("切图参数超过图片尺寸")
        cell_width = usable_width // cols
        cell_height = usable_height // rows
        slot_by_cell = {slot["cell_id"]: slot for slot in sheet.get("slots", [])}
        for row in range(1, rows + 1):
            for col in range(1, cols + 1):
                cell_id = f"r{row:02d}c{col:02d}"
                slot = slot_by_cell.get(cell_id)
                if not slot:
                    continue
                left = padding + (col - 1) * (cell_width + gap)
                top = padding + (row - 1) * (cell_height + gap)
                right = left + cell_width
                bottom = top + cell_height
                tile = image.crop((left, top, right, bottom))
                tile_path = tile_root / f"{cell_id}.png"
                tile.save(tile_path)
                tiles.append(
                    {
                        "cell_id": cell_id,
                        "row": row,
                        "col": col,
                        "kind": slot.get("kind", "bound"),
                        "item_id": slot.get("item_id"),
                        "target_item_id": existing_tiles.get(cell_id, {}).get("target_item_id") or slot.get("item_id"),
                        "image_path": f"images/tiles/{cell_id}.png",
                        "status": "split",
                        "review_status": existing_tiles.get(cell_id, {}).get("review_status", "pending"),
                        "promoted_version": existing_tiles.get(cell_id, {}).get("promoted_version"),
                        "starred": bool(existing_tiles.get(cell_id, {}).get("starred", False)),
                    }
                )

    sheet["status"] = "split"
    sheet["split_config"] = {
        "rows": rows,
        "cols": cols,
        "padding": padding,
        "gap": gap,
    }
    sheet["tiles"] = tiles
    save_sheet(task_id, sheet)
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": "split_grid_sheet",
            "sheet_id": sheet_id,
            "tile_count": len(tiles),
        },
    )
    return sheet


def _find_tile(sheet: dict, cell_id: str) -> dict:
    for tile in sheet.get("tiles") or []:
        if tile.get("cell_id") == cell_id:
            return tile
    raise ValueError(f"Tile not found: {sheet.get('sheet_id')} {cell_id}")


def review_grid_sheet_tile(
    task_id: str,
    sheet_id: str,
    cell_id: str,
    *,
    review_status: str,
    target_item_id: str | None = None,
    source: str = "cli",
) -> dict:
    normalized_status = review_status.strip().lower()
    if normalized_status not in TILE_REVIEW_STATUSES:
        raise ValueError(f"Unsupported tile review status: {review_status}")
    sheet = load_sheet(task_id, sheet_id)
    tile = _find_tile(sheet, cell_id)
    if target_item_id:
        load_item(task_id, target_item_id)
        tile["target_item_id"] = target_item_id
    else:
        tile.setdefault("target_item_id", tile.get("item_id"))
    tile["review_status"] = normalized_status
    save_sheet(task_id, sheet)
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": "review_grid_sheet_tile",
            "sheet_id": sheet_id,
            "cell_id": cell_id,
            "review_status": normalized_status,
            "target_item_id": tile.get("target_item_id"),
        },
    )
    return sheet


def _promote_grid_sheet_tile(
    task_id: str,
    sheet: dict,
    tile: dict,
    *,
    target_item_id: str | None = None,
    starred: bool = True,
    source: str = "cli",
) -> dict | None:
    sheet_id = sheet["sheet_id"]
    resolved_item_id = target_item_id or tile.get("target_item_id") or tile.get("item_id")
    if not resolved_item_id:
        raise ValueError(f"Tile has no target item: {sheet_id} {tile.get('cell_id')}")
    source_path = sheet_dir(task_id, sheet_id) / tile["image_path"]
    if not source_path.exists():
        return None
    item = load_item(task_id, resolved_item_id)
    destination_name = f"{sheet_id}_{tile['cell_id']}.png"
    destination = item_dir(task_id, resolved_item_id) / "images" / destination_name
    ensure_dir(destination.parent)
    shutil.copyfile(source_path, destination)
    payload = {
        "step": STEP_IMAGE_GENERATION,
        "provider": "grid_sheet",
        "model": sheet.get("model"),
        "created_at": utc_now(),
        "input": {
            "source": "grid_sheet",
            "sheet_id": sheet_id,
            "cell_id": tile["cell_id"],
            "review_status": "selected",
        },
        "output": {
            "candidates": [
                {
                    "candidate_id": f"{sheet_id}_{tile['cell_id']}",
                    "image_path": destination_name,
                    "source": "grid_sheet",
                    "sheet_id": sheet_id,
                    "cell_id": tile["cell_id"],
                    "row": tile.get("row"),
                    "col": tile.get("col"),
                }
            ]
        },
    }
    version = write_artifact(task_id, resolved_item_id, STEP_IMAGE_GENERATION, payload)
    item["current_versions"][STEP_IMAGE_GENERATION] = version
    if starred:
        starred_versions = list(dict.fromkeys(item.get("starred_image_versions", [])))
        if version not in starred_versions:
            starred_versions.append(version)
        item["starred_image_versions"] = starred_versions
    item["status"] = STATUS_IMAGE_GENERATED
    save_item(task_id, item)
    metrics = load_metrics(task_id, resolved_item_id)
    metrics["status"] = STATUS_IMAGE_GENERATED
    metrics["end_time"] = None
    metrics["iterations"][STEP_IMAGE_GENERATION] += 1
    save_metrics(task_id, resolved_item_id, metrics)
    tile["review_status"] = "selected"
    tile["target_item_id"] = resolved_item_id
    tile["promoted_version"] = version
    tile["starred"] = bool(starred)
    append_item_event(
        task_id,
        resolved_item_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": "promote_grid_sheet_tile",
            "sheet_id": sheet_id,
            "cell_id": tile["cell_id"],
            "version": version,
            "starred": bool(starred),
            "to": STATUS_IMAGE_GENERATED,
        },
    )
    return {"item_id": resolved_item_id, "cell_id": tile["cell_id"], "version": version, "starred": bool(starred)}


def promote_grid_sheet_tile(
    task_id: str,
    sheet_id: str,
    cell_id: str,
    *,
    target_item_id: str | None = None,
    starred: bool = True,
    source: str = "cli",
) -> dict:
    sheet = load_sheet(task_id, sheet_id)
    tile = _find_tile(sheet, cell_id)
    result = _promote_grid_sheet_tile(
        task_id,
        sheet,
        tile,
        target_item_id=target_item_id,
        starred=starred,
        source=source,
    )
    if not result:
        raise ValueError(f"Tile image not found: {cell_id}")
    sheet.setdefault("backfilled", [])
    sheet["backfilled"].append(result)
    sheet["status"] = "reviewing"
    save_sheet(task_id, sheet)
    refresh_task_summary(task_id)
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": "promote_grid_sheet_tile",
            "sheet_id": sheet_id,
            "cell_id": cell_id,
            "target_item_id": result["item_id"],
            "version": result["version"],
        },
    )
    return sheet


def create_item_from_grid_sheet_tile(
    task_id: str,
    sheet_id: str,
    cell_id: str,
    *,
    title: str,
    description: str = "",
    asset_type: str = "skill_icon",
    category: str = "emergent",
    starred: bool = True,
    source: str = "cli",
) -> dict:
    item = create_item(
        task_id,
        asset_type=asset_type,
        title=title,
        description=description,
        category=category,
        extra_context=f"Created from grid sheet {sheet_id} {cell_id}",
    )
    sheet = promote_grid_sheet_tile(
        task_id,
        sheet_id,
        cell_id,
        target_item_id=item["item_id"],
        starred=starred,
        source=source,
    )
    tile = _find_tile(sheet, cell_id)
    tile["created_item_id"] = item["item_id"]
    save_sheet(task_id, sheet)
    return sheet


def backfill_grid_sheet(task_id: str, sheet_id: str, *, source: str = "cli") -> dict:
    sheet = load_sheet(task_id, sheet_id)
    tiles = sheet.get("tiles") or []
    if not tiles:
        raise ValueError("当前 sheet 还没有可回填的 tile")
    backfilled = []
    for tile in tiles:
        if tile.get("review_status") != "selected" or tile.get("promoted_version"):
            continue
        result = _promote_grid_sheet_tile(task_id, sheet, tile, source=source)
        if result:
            backfilled.append(result)

    if not backfilled:
        raise ValueError("当前 sheet 没有已采纳且未回填的 tile")
    sheet["status"] = "backfilled"
    sheet["backfilled"] = list(sheet.get("backfilled") or []) + backfilled
    save_sheet(task_id, sheet)
    refresh_task_summary(task_id)
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": "backfill_grid_sheet",
            "sheet_id": sheet_id,
            "count": len(backfilled),
        },
    )
    return sheet
