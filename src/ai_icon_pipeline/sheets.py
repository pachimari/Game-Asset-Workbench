from __future__ import annotations

from pathlib import Path
import re
import shutil

from PIL import Image

from .config import (
    STATUS_IMAGE_GENERATED,
    STEP_BRIEF_GENERATION,
    STEP_IMAGE_GENERATION,
)
from .providers.registry import get_async_image_provider
from .settings import load_global_settings, provider_settings_for, resolve_stage_selection
from .storage import (
    PENDING_ASYNC_STATUSES,
    append_event,
    append_item_event,
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
                "item_id": slot["item_id"],
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

    prompt = f"""Create one complete game asset icon grid sheet.

Canvas and grid:
- Exact grid: {rows} rows x {cols} columns, {rows * cols} equal cells.
- Fill cells in row-major order from left to right, top to bottom.
- Keep each cell visually separated with clear empty space or subtle separators.
- Each cell must contain exactly one independent asset subject.
- Do not let any subject cross cell boundaries.
- Do not add text, labels, numbering, watermarks, logos, signatures, captions, UI badges, or extra symbols.

Style:
- Project background: {task.get('project_background', '')}
- Unified style requirements: {task.get('style_requirements', '')}
- Use consistent camera angle, lighting, material rendering, background treatment, and icon scale across the whole sheet.
- Prefer centered subjects, readable silhouettes, and simple backgrounds suitable for later tile cropping.

Cell assignments:
{chr(10).join(slot_lines)}

Empty cells:
- If the grid has more cells than assignments, keep remaining cells visually empty and unobtrusive.
"""
    negative_prompt = (
        "text, labels, numbers, watermark, signature, logo, subject crossing cell boundaries, "
        "merged cells, uneven grid, duplicated unrelated objects, busy background, cropped subject"
    )
    return {
        "mode": "grid_sheet",
        "brief_strategy": "slot briefs use approved item brief when available, otherwise raw item input",
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
                "item_id": item["item_id"],
                "title": item.get("title", ""),
                "brief": brief,
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
            "remaining_item_count": max(0, len(items) - len(selected_items)),
        },
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
                        "item_id": slot["item_id"],
                        "image_path": f"images/tiles/{cell_id}.png",
                        "status": "split",
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


def backfill_grid_sheet(task_id: str, sheet_id: str, *, source: str = "cli") -> dict:
    sheet = load_sheet(task_id, sheet_id)
    tiles = sheet.get("tiles") or []
    if not tiles:
        raise ValueError("当前 sheet 还没有可回填的 tile")
    backfilled = []
    for tile in tiles:
        item_id = tile.get("item_id")
        if not item_id:
            continue
        source_path = sheet_dir(task_id, sheet_id) / tile["image_path"]
        if not source_path.exists():
            continue
        item = load_item(task_id, item_id)
        destination_name = f"{sheet_id}_{tile['cell_id']}.png"
        destination = item_dir(task_id, item_id) / "images" / destination_name
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
        version = write_artifact(task_id, item_id, STEP_IMAGE_GENERATION, payload)
        item["current_versions"][STEP_IMAGE_GENERATION] = version
        item["status"] = STATUS_IMAGE_GENERATED
        save_item(task_id, item)
        metrics = load_metrics(task_id, item_id)
        metrics["status"] = STATUS_IMAGE_GENERATED
        metrics["end_time"] = None
        metrics["iterations"][STEP_IMAGE_GENERATION] += 1
        save_metrics(task_id, item_id, metrics)
        append_item_event(
            task_id,
            item_id,
            {
                "timestamp": utc_now(),
                "source": source,
                "action": "backfill_grid_sheet_tile",
                "sheet_id": sheet_id,
                "cell_id": tile["cell_id"],
                "version": version,
                "to": STATUS_IMAGE_GENERATED,
            },
        )
        backfilled.append({"item_id": item_id, "cell_id": tile["cell_id"], "version": version})

    sheet["status"] = "backfilled"
    sheet["backfilled"] = backfilled
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
