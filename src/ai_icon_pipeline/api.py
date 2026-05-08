from __future__ import annotations

import logging
import hmac
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .config import (
    API_ALLOWED_ORIGINS,
    API_ALLOW_REMOTE,
    API_PUBLIC_ERROR_DETAILS,
    API_TOKEN,
)
from .pipeline import (
    approve_step,
    cancel_pending_image_generations,
    edit_brief,
    edit_prompt,
    poll_image_generation,
    poll_image_generation_version,
    rollback_step,
    run_pipeline,
    run_step,
    set_current_version,
)
from .providers.registry import sync_provider_models
from .settings import (
    create_custom_provider,
    delete_custom_provider,
    load_global_settings,
    save_global_settings,
    update_prompt_templates,
    update_provider_settings,
)
from .sheets import (
    backfill_grid_sheet,
    create_item_from_grid_sheet_tile,
    list_sheets,
    load_sheet,
    plan_grid_sheet,
    poll_grid_sheet_generation,
    promote_grid_sheet_tile,
    review_grid_sheet_tile,
    sheet_dir,
    split_grid_sheet,
    submit_grid_sheet_generation,
)
from .storage import (
    TASKS_DIR,
    create_item,
    create_task,
    delete_task,
    export_starred_images_zip,
    compute_batch_metrics,
    item_dir,
    list_artifacts,
    list_items,
    list_tasks,
    load_artifact,
    load_item,
    load_item_chat,
    load_item_events,
    load_runtime_config,
    load_task,
    summarize_item_images,
    update_item,
    update_item_model_override,
    update_item_starred_versions,
    update_runtime_config,
    update_task_model_override,
    update_task_settings,
)
from .utils import utc_now

logger = logging.getLogger(__name__)


class TaskCreatePayload(BaseModel):
    task_name: str
    project_background: str = ""
    style_requirements: str = ""
    asset_domain: str = "game_icon_assets"
    image_generation_mode: str = "single"
    image_aspect_ratio: str = "1:1"
    image_resolution: str = "1K"
    grid_rows: int = 8
    grid_cols: int = 8
    grid_padding: int = 0
    grid_gap: int = 0


class TaskUpdatePayload(BaseModel):
    task_name: Optional[str] = None
    project_background: Optional[str] = None
    style_requirements: Optional[str] = None
    asset_domain: Optional[str] = None
    brief_provider: Optional[str] = None
    brief_model: Optional[str] = None
    prompt_provider: Optional[str] = None
    prompt_model: Optional[str] = None
    image_provider: Optional[str] = None
    image_model: Optional[str] = None
    image_aspect_ratio: Optional[str] = None
    image_resolution: Optional[str] = None
    image_generation_mode: Optional[str] = None
    grid_rows: Optional[int] = None
    grid_cols: Optional[int] = None
    grid_padding: Optional[int] = None
    grid_gap: Optional[int] = None


class ItemCreatePayload(BaseModel):
    asset_type: str = "generic_icon"
    title: str = ""
    description: str = ""
    category: str = ""
    extra_context: str = ""
    image_aspect_ratio: Optional[str] = None
    image_resolution: Optional[str] = None


class ItemUpdatePayload(BaseModel):
    asset_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    extra_context: Optional[str] = None
    image_aspect_ratio: Optional[str] = None
    image_resolution: Optional[str] = None
    brief_provider: Optional[str] = None
    brief_model: Optional[str] = None
    prompt_provider: Optional[str] = None
    prompt_model: Optional[str] = None
    image_provider: Optional[str] = None
    image_model: Optional[str] = None


class StepActionPayload(BaseModel):
    source: str = "web"


class BriefEditPayload(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    visual_focus: Optional[str] = None
    keywords: Optional[list[str]] = None
    note: Optional[str] = None


class PromptEditPayload(BaseModel):
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    note: Optional[str] = None


class VersionSelectPayload(BaseModel):
    version: str
    source: str = "web"


class CandidateStarPayload(BaseModel):
    version: str
    starred: bool = True
    source: str = "web"


class ImagePollPayload(BaseModel):
    source: str = "web"
    version: Optional[str] = None


class ProviderCreatePayload(BaseModel):
    label: str
    provider_type: str
    base_url: str = ""
    api_key: Optional[str] = None
    image_max_concurrency: Optional[int] = None


class ProviderUpdatePayload(BaseModel):
    label: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    image_max_concurrency: Optional[int] = None


class SettingsDefaultsPayload(BaseModel):
    brief_provider: Optional[str] = None
    brief_model: Optional[str] = None
    prompt_provider: Optional[str] = None
    prompt_model: Optional[str] = None
    image_provider: Optional[str] = None
    image_model: Optional[str] = None


class PromptTemplatesPayload(BaseModel):
    brief_system_prompt: Optional[str] = None
    prompt_system_prompt: Optional[str] = None
    grid_sheet_prompt_template: Optional[str] = None
    grid_sheet_negative_prompt: Optional[str] = None


class TaskPipelinePayload(BaseModel):
    auto_approve: bool = True
    source: str = "web"
    image_concurrency: Optional[int] = None


class SheetActionPayload(BaseModel):
    source: str = "web"


class SheetSplitPayload(SheetActionPayload):
    crop_box_percent: Optional[dict[str, float]] = None
    x_lines_percent: Optional[list[float]] = None
    y_lines_percent: Optional[list[float]] = None


class SheetTileReviewPayload(BaseModel):
    review_status: str
    target_item_id: Optional[str] = None
    source: str = "web"


class SheetTilePromotePayload(BaseModel):
    target_item_id: Optional[str] = None
    starred: bool = True
    source: str = "web"


class SheetTileCreateItemPayload(BaseModel):
    title: str
    description: str = ""
    asset_type: str = "skill_icon"
    category: str = "emergent"
    starred: bool = True
    source: str = "web"


def _to_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    message = str(exc)
    if "not found" in message.lower():
        return HTTPException(status_code=404, detail=message)
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=message)

    logger.exception("Unhandled API error")
    detail = message if API_PUBLIC_ERROR_DETAILS else "Internal server error"
    return HTTPException(status_code=500, detail=detail)


def _apply_task_model_overrides(task_id: str, payload: TaskUpdatePayload) -> None:
    provided = getattr(payload, "model_fields_set", set())
    overrides = [
        ("brief_generation", "brief_provider", "brief_model"),
        ("image_prompt", "prompt_provider", "prompt_model"),
        ("image_generation", "image_provider", "image_model"),
    ]
    for step, provider_field, model_field in overrides:
        if provider_field in provided or model_field in provided:
            provider = getattr(payload, provider_field)
            model = getattr(payload, model_field)
            update_task_model_override(task_id, step, provider=provider, model=model)


def _apply_item_model_overrides(task_id: str, item_id: str, payload: ItemUpdatePayload) -> None:
    provided = getattr(payload, "model_fields_set", set())
    overrides = [
        ("brief_generation", "brief_provider", "brief_model"),
        ("image_prompt", "prompt_provider", "prompt_model"),
        ("image_generation", "image_provider", "image_model"),
    ]
    for step, provider_field, model_field in overrides:
        if provider_field in provided or model_field in provided:
            provider = getattr(payload, provider_field)
            model = getattr(payload, model_field)
            update_item_model_override(task_id, item_id, step, provider=provider, model=model)


def _settings_payload() -> dict:
    settings = load_global_settings()
    defaults = settings.get("defaults", {})
    prompt_templates = settings.get("prompt_templates", {})

    provider_details = []
    for provider_id, config in settings.get("providers", {}).items():
        provider_details.append(
            {
                "id": provider_id,
                "label": config.get("label", provider_id),
                "provider_type": config.get("provider_type"),
                "base_url": config.get("base_url", ""),
                "builtin": True,
                "api_key_masked": _mask_api_key(config.get("api_key", "")),
                "models": config.get("models", []),
                "image_max_concurrency": config.get("image_max_concurrency"),
                "last_synced_at": config.get("last_synced_at"),
                "last_error": config.get("last_error"),
            }
        )
    for config in settings.get("custom_providers", []):
        provider_details.append(
            {
                "id": config.get("id"),
                "label": config.get("label", config.get("id")),
                "provider_type": config.get("provider_type"),
                "base_url": config.get("base_url", ""),
                "builtin": False,
                "api_key_masked": _mask_api_key(config.get("api_key", "")),
                "models": config.get("models", []),
                "image_max_concurrency": config.get("image_max_concurrency"),
                "last_synced_at": config.get("last_synced_at"),
                "last_error": config.get("last_error"),
            }
        )

    return {
        "defaults": defaults,
        "prompt_templates": prompt_templates,
        "providers": provider_details,
    }


def _mask_api_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "\u2022" * (len(key) - 8) + key[-4:]


def _file_url(path: Path) -> str:
    relative = path.relative_to(TASKS_DIR)
    return f"/files/{relative.as_posix()}"


def _safe_file_response_path(file_path: str) -> Path:
    target = (TASKS_DIR / file_path).resolve()
    tasks_root = TASKS_DIR.resolve()
    try:
        target.relative_to(tasks_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Unsafe file path") from exc
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    relative = target.relative_to(tasks_root)
    parts = relative.parts
    allowed = (
        "images" in parts
        or (len(parts) >= 2 and parts[1] == "exports")
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="File access is restricted")
    return target


def _download_filename_fragment(value: str) -> str:
    cleaned = value.strip().replace("/", "_").replace("\\", "_")
    cleaned = " ".join(cleaned.split())
    return cleaned[:80] or "batch"


def _download_headers(filename_utf8: str, fallback_ascii: str) -> dict[str, str]:
    quoted = fallback_ascii.replace('"', "")
    return {
        "Content-Disposition": (
            f'attachment; filename="{quoted}"; '
            f"filename*=UTF-8''{quote(filename_utf8)}"
        )
    }


def _client_host(request: Request) -> str:
    return request.client.host if request.client else ""


def _normalized_host(value: str) -> str:
    candidate = value.strip()
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    elif candidate.count(":") == 1:
        host, port = candidate.rsplit(":", 1)
        if port.isdigit():
            candidate = host
    return candidate


def _forwarded_client_host(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return _normalized_host(first)
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return _normalized_host(real_ip)
    return ""


def _is_local_host(host: str) -> bool:
    return host in {"127.0.0.1", "::1", "localhost"}


def _is_local_request(request: Request) -> bool:
    host = _normalized_host(_client_host(request))
    if not _is_local_host(host):
        return False
    forwarded_host = _forwarded_client_host(request)
    if forwarded_host:
        return _is_local_host(forwarded_host)
    return True


def _check_request_access(request: Request) -> None:
    if request.url.path == "/health":
        return
    if not API_ALLOW_REMOTE and not _is_local_request(request):
        raise HTTPException(status_code=403, detail="Remote access is disabled")

    if API_TOKEN:
        bearer = request.headers.get("authorization", "")
        token = request.headers.get("x-api-key", "")
        if bearer.startswith("Bearer "):
            token = bearer.removeprefix("Bearer ").strip()
        if not hmac.compare_digest(token, API_TOKEN):
            raise HTTPException(status_code=401, detail="Unauthorized")


def _candidate_rows(task_id: str, item_id: str) -> dict:
    item = load_item(task_id, item_id)
    starred_versions = set(item.get("starred_image_versions", []))
    rows: list[dict] = []
    approved_url = None
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = item_dir(task_id, item_id) / "images" / f"approved{suffix}"
        if candidate.exists():
            approved_url = _file_url(candidate)
            break

    for meta in reversed(list_artifacts(task_id, item_id, "image_generation")):
        artifact = meta.get("_payload")
        if not isinstance(artifact, dict):
            artifact = load_artifact(task_id, item_id, "image_generation", meta["version"])
        async_job = artifact.get("async_job") or {}
        output = artifact.get("output") or {}
        candidates = []
        for candidate in output.get("candidates", []):
            image_path = candidate.get("image_path")
            image_url = None
            if image_path:
                image_url = _file_url(item_dir(task_id, item_id) / "images" / image_path)
            candidates.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "image_path": image_path,
                    "image_url": image_url,
                    "source_url": candidate.get("source_url"),
                    "source": candidate.get("source"),
                    "sheet_id": candidate.get("sheet_id"),
                    "cell_id": candidate.get("cell_id"),
                    "row": candidate.get("row"),
                    "col": candidate.get("col"),
                }
            )
        rows.append(
            {
                "version": artifact.get("version", meta["version"]),
                "provider": artifact.get("provider"),
                "model": artifact.get("model"),
                "created_at": artifact.get("created_at"),
                "is_current": item["current_versions"].get("image_generation")
                == artifact.get("version", meta["version"]),
                "is_starred": artifact.get("version", meta["version"]) in starred_versions,
                "async_job": async_job or None,
                "candidates": candidates,
            }
        )

    return {
        "approved_image_url": approved_url,
        "versions": rows,
    }


def _artifact_snapshot(task_id: str, item_id: str, step: str, version: str | None) -> dict | None:
    if not version:
        return None
    artifact = load_artifact(task_id, item_id, step, version)
    return {
        "version": artifact.get("version", version),
        "provider": artifact.get("provider"),
        "model": artifact.get("model"),
        "created_at": artifact.get("created_at"),
        "input": artifact.get("input"),
        "output": artifact.get("output"),
    }


def _item_preview_url(task_id: str, item_id: str) -> str | None:
    candidate_rows = _candidate_rows(task_id, item_id)
    if candidate_rows.get("approved_image_url"):
        return candidate_rows["approved_image_url"]
    for version in candidate_rows.get("versions", []):
        for candidate in version.get("candidates", []):
            if candidate.get("image_url"):
                return candidate["image_url"]
    return None


def _item_summary_payload(task_id: str, item: dict) -> dict:
    payload = dict(item)
    image_summary = summarize_item_images(task_id, item["item_id"])
    preview_path = image_summary.get("preview_image_path")
    payload["preview_image_url"] = _file_url(preview_path) if isinstance(preview_path, Path) else None
    payload["pending_image_jobs"] = int(image_summary.get("pending_image_jobs", 0))
    return payload


def _workspace_payload(task_id: str, item_id: str) -> dict:
    item = load_item(task_id, item_id)
    brief_version = item["current_versions"].get("brief_generation")
    prompt_version = item["current_versions"].get("image_prompt")
    image_version = item["current_versions"].get("image_generation")

    return {
        "task_id": task_id,
        "item_id": item_id,
        "status": item.get("status"),
        "current_versions": item.get("current_versions", {}),
        "brief": _artifact_snapshot(task_id, item_id, "brief_generation", brief_version),
        "prompt": _artifact_snapshot(task_id, item_id, "image_prompt", prompt_version),
        "current_image_version": image_version,
        "candidate_pool": _candidate_rows(task_id, item_id),
        "events": load_item_events(task_id, item_id)[-20:],
        "chat": load_item_chat(task_id, item_id)[-20:],
    }


def _task_payload(task_id: str) -> dict:
    task = load_task(task_id)
    task["runtime_config"] = load_runtime_config(task_id)
    task["batch_metrics"] = compute_batch_metrics(task_id)
    return task


def _sheet_payload(task_id: str, sheet: dict) -> dict:
    payload = dict(sheet)
    root = sheet_dir(task_id, sheet["sheet_id"])
    source_image_path = payload.get("source_image_path")
    payload["source_image_url"] = _file_url(root / source_image_path) if source_image_path else None
    tiles = []
    for tile in payload.get("tiles", []):
        row = dict(tile)
        image_path = row.get("image_path")
        row["image_url"] = _file_url(root / image_path) if image_path else None
        tiles.append(row)
    payload["tiles"] = tiles
    return payload


def _provider_rows() -> list[dict]:
    settings = load_global_settings()
    rows: list[dict] = []
    for provider_id, config in settings.get("providers", {}).items():
        rows.append(
            {
                "id": provider_id,
                "label": config.get("label", provider_id),
                "provider_type": config.get("provider_type"),
                "base_url": config.get("base_url", ""),
                "model_count": len(config.get("models", [])),
                "image_max_concurrency": config.get("image_max_concurrency"),
                "builtin": True,
                "last_synced_at": config.get("last_synced_at"),
                "last_error": config.get("last_error"),
            }
        )
    for config in settings.get("custom_providers", []):
        provider_id = config.get("id")
        rows.append(
            {
                "id": provider_id,
                "label": config.get("label", provider_id),
                "provider_type": config.get("provider_type"),
                "base_url": config.get("base_url", ""),
                "model_count": len(config.get("models", [])),
                "image_max_concurrency": config.get("image_max_concurrency"),
                "builtin": False,
                "last_synced_at": config.get("last_synced_at"),
                "last_error": config.get("last_error"),
            }
        )
    return rows


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Icon Pipeline API",
        version="0.5.0",
        description="Thin local API layer for the M5 formal web UI.",
    )

    if API_ALLOWED_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=API_ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def local_only_and_auth(request: Request, call_next):
        _check_request_access(request)
        return await call_next(request)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "service": "ai-icon-pipeline-api"}

    @app.get("/files/{file_path:path}")
    def get_file(file_path: str) -> FileResponse:
        path = _safe_file_response_path(file_path)
        return FileResponse(path)

    @app.get("/tasks")
    def get_tasks() -> dict:
        return {"tasks": list_tasks()}

    @app.get("/tasks/{task_id}")
    def get_task(task_id: str) -> dict:
        try:
            return _task_payload(task_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/tasks/{task_id}/items")
    def get_task_items(task_id: str) -> dict:
        try:
            return {
                "task_id": task_id,
                "items": [_item_summary_payload(task_id, item) for item in list_items(task_id)],
            }
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/tasks/{task_id}/items/{item_id}")
    def get_task_item(task_id: str, item_id: str) -> dict:
        try:
            return _item_summary_payload(task_id, load_item(task_id, item_id))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/tasks/{task_id}/items/{item_id}/workspace")
    def get_task_item_workspace(task_id: str, item_id: str) -> dict:
        try:
            return _workspace_payload(task_id, item_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/providers")
    def get_providers() -> dict:
        return {"providers": _provider_rows()}

    @app.get("/settings")
    def get_settings() -> dict:
        return _settings_payload()

    @app.post("/tasks")
    async def post_task(payload: TaskCreatePayload) -> dict:
        task = await run_in_threadpool(
            create_task,
            task_name=payload.task_name,
            project_background=payload.project_background,
            style_requirements=payload.style_requirements,
            asset_domain=payload.asset_domain,
            runtime_config={
                "image_generation_mode": payload.image_generation_mode,
                "image_aspect_ratio": payload.image_aspect_ratio,
                "image_resolution": payload.image_resolution,
                "grid_rows": payload.grid_rows,
                "grid_cols": payload.grid_cols,
                "grid_padding": payload.grid_padding,
                "grid_gap": payload.grid_gap,
            },
        )
        return _task_payload(task["task_id"])

    @app.patch("/tasks/{task_id}")
    async def patch_task(task_id: str, payload: TaskUpdatePayload) -> dict:
        try:
            await run_in_threadpool(
                update_task_settings,
                task_id,
                task_name=payload.task_name,
                project_background=payload.project_background,
                style_requirements=payload.style_requirements,
                asset_domain=payload.asset_domain,
            )
            _apply_task_model_overrides(task_id, payload)
            runtime_fields = (
                payload.image_aspect_ratio,
                payload.image_resolution,
                payload.image_generation_mode,
                payload.grid_rows,
                payload.grid_cols,
                payload.grid_padding,
                payload.grid_gap,
            )
            if any(value is not None for value in runtime_fields):
                await run_in_threadpool(
                    update_runtime_config,
                    task_id,
                    image_aspect_ratio=payload.image_aspect_ratio,
                    image_resolution=payload.image_resolution,
                    image_generation_mode=payload.image_generation_mode,
                    grid_rows=payload.grid_rows,
                    grid_cols=payload.grid_cols,
                    grid_padding=payload.grid_padding,
                    grid_gap=payload.grid_gap,
                )
            return _task_payload(task_id)
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.delete("/tasks/{task_id}")
    async def delete_task_route(task_id: str) -> dict:
        try:
            await run_in_threadpool(delete_task, task_id)
            return {"ok": True, "task_id": task_id}
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.get("/tasks/{task_id}/exports/starred-images.zip")
    async def get_task_starred_images_export(task_id: str) -> FileResponse:
        try:
            archive_path = await run_in_threadpool(export_starred_images_zip, task_id)
            task = load_task(task_id)
            filename = f"{_download_filename_fragment(task.get('task_name', task_id))}_starred-images.zip"
            return FileResponse(
                archive_path,
                media_type="application/zip",
                headers=_download_headers(
                    f"{_download_filename_fragment(task.get('task_name', task_id))}_星标图.zip",
                    filename,
                ),
            )
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.get("/tasks/{task_id}/sheets")
    async def get_task_sheets(task_id: str) -> dict:
        try:
            return {
                "task_id": task_id,
                "sheets": [_sheet_payload(task_id, sheet) for sheet in list_sheets(task_id)],
            }
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.get("/tasks/{task_id}/sheets/{sheet_id}")
    async def get_task_sheet(task_id: str, sheet_id: str) -> dict:
        try:
            return _sheet_payload(task_id, load_sheet(task_id, sheet_id))
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/sheets/plan")
    async def post_plan_grid_sheet(task_id: str, payload: SheetActionPayload) -> dict:
        try:
            sheet = await run_in_threadpool(plan_grid_sheet, task_id, source=payload.source)
            return {
                "sheet": _sheet_payload(task_id, sheet),
                "task": _task_payload(task_id),
                "items": [_item_summary_payload(task_id, item) for item in list_items(task_id)],
            }
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/sheets/{sheet_id}/generate")
    async def post_generate_grid_sheet(task_id: str, sheet_id: str, payload: SheetActionPayload) -> dict:
        try:
            sheet = await run_in_threadpool(
                submit_grid_sheet_generation,
                task_id,
                sheet_id,
                source=payload.source,
            )
            return {"sheet": _sheet_payload(task_id, sheet)}
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/sheets/{sheet_id}/poll")
    async def post_poll_grid_sheet(task_id: str, sheet_id: str, payload: SheetActionPayload) -> dict:
        try:
            sheet = await run_in_threadpool(
                poll_grid_sheet_generation,
                task_id,
                sheet_id,
                source=payload.source,
            )
            return {"sheet": _sheet_payload(task_id, sheet)}
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/sheets/{sheet_id}/split")
    async def post_split_grid_sheet(task_id: str, sheet_id: str, payload: SheetSplitPayload) -> dict:
        try:
            sheet = await run_in_threadpool(
                split_grid_sheet,
                task_id,
                sheet_id,
                crop_box_percent=payload.crop_box_percent,
                x_lines_percent=payload.x_lines_percent,
                y_lines_percent=payload.y_lines_percent,
                source=payload.source,
            )
            return {"sheet": _sheet_payload(task_id, sheet)}
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/sheets/{sheet_id}/backfill")
    async def post_backfill_grid_sheet(task_id: str, sheet_id: str, payload: SheetActionPayload) -> dict:
        try:
            sheet = await run_in_threadpool(
                backfill_grid_sheet,
                task_id,
                sheet_id,
                source=payload.source,
            )
            return {
                "sheet": _sheet_payload(task_id, sheet),
                "task": _task_payload(task_id),
                "items": [_item_summary_payload(task_id, item) for item in list_items(task_id)],
            }
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/sheets/{sheet_id}/tiles/{cell_id}/review")
    async def post_review_grid_sheet_tile(
        task_id: str,
        sheet_id: str,
        cell_id: str,
        payload: SheetTileReviewPayload,
    ) -> dict:
        try:
            sheet = await run_in_threadpool(
                review_grid_sheet_tile,
                task_id,
                sheet_id,
                cell_id,
                review_status=payload.review_status,
                target_item_id=payload.target_item_id,
                source=payload.source,
            )
            return {"sheet": _sheet_payload(task_id, sheet)}
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/sheets/{sheet_id}/tiles/{cell_id}/promote")
    async def post_promote_grid_sheet_tile(
        task_id: str,
        sheet_id: str,
        cell_id: str,
        payload: SheetTilePromotePayload,
    ) -> dict:
        try:
            sheet = await run_in_threadpool(
                promote_grid_sheet_tile,
                task_id,
                sheet_id,
                cell_id,
                target_item_id=payload.target_item_id,
                starred=payload.starred,
                source=payload.source,
            )
            return {
                "sheet": _sheet_payload(task_id, sheet),
                "task": _task_payload(task_id),
                "items": [_item_summary_payload(task_id, item) for item in list_items(task_id)],
            }
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/sheets/{sheet_id}/tiles/{cell_id}/create-item")
    async def post_create_item_from_grid_sheet_tile(
        task_id: str,
        sheet_id: str,
        cell_id: str,
        payload: SheetTileCreateItemPayload,
    ) -> dict:
        try:
            sheet = await run_in_threadpool(
                create_item_from_grid_sheet_tile,
                task_id,
                sheet_id,
                cell_id,
                title=payload.title,
                description=payload.description,
                asset_type=payload.asset_type,
                category=payload.category,
                starred=payload.starred,
                source=payload.source,
            )
            return {
                "sheet": _sheet_payload(task_id, sheet),
                "task": _task_payload(task_id),
                "items": [_item_summary_payload(task_id, item) for item in list_items(task_id)],
            }
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/items")
    async def post_item(task_id: str, payload: ItemCreatePayload) -> dict:
        try:
            return await run_in_threadpool(
                create_item,
                task_id,
                asset_type=payload.asset_type,
                title=payload.title,
                description=payload.description,
                category=payload.category,
                extra_context=payload.extra_context,
                image_aspect_ratio=payload.image_aspect_ratio,
                image_resolution=payload.image_resolution,
            )
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.patch("/tasks/{task_id}/items/{item_id}")
    async def patch_item(task_id: str, item_id: str, payload: ItemUpdatePayload) -> dict:
        try:
            await run_in_threadpool(
                update_item,
                task_id,
                item_id,
                asset_type=payload.asset_type,
                title=payload.title,
                description=payload.description,
                category=payload.category,
                extra_context=payload.extra_context,
                image_aspect_ratio=payload.image_aspect_ratio,
                image_resolution=payload.image_resolution,
            )
            _apply_item_model_overrides(task_id, item_id, payload)
            return load_item(task_id, item_id)
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/items/{item_id}/brief/edit")
    async def post_edit_brief(task_id: str, item_id: str, payload: BriefEditPayload) -> dict:
        try:
            result = await run_in_threadpool(
                edit_brief,
                task_id,
                item_id,
                title=payload.title,
                description=payload.description,
                keywords=payload.keywords,
                visual_focus=payload.visual_focus,
                note=payload.note,
                source="web",
            )
            return {"result": result, "workspace": _workspace_payload(task_id, item_id)}
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/items/{item_id}/prompt/edit")
    async def post_edit_prompt(task_id: str, item_id: str, payload: PromptEditPayload) -> dict:
        try:
            result = await run_in_threadpool(
                edit_prompt,
                task_id,
                item_id,
                prompt=payload.prompt,
                negative_prompt=payload.negative_prompt,
                note=payload.note,
                source="web",
            )
            return {"result": result, "workspace": _workspace_payload(task_id, item_id)}
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/items/{item_id}/steps/{step}/run")
    async def post_run_step(task_id: str, item_id: str, step: str, payload: StepActionPayload) -> dict:
        try:
            result = await run_in_threadpool(run_step, task_id, item_id, step, source=payload.source)
            return {"result": result, "workspace": _workspace_payload(task_id, item_id)}
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/items/{item_id}/steps/{step}/select-version")
    async def post_select_version(
        task_id: str,
        item_id: str,
        step: str,
        payload: VersionSelectPayload,
    ) -> dict:
        try:
            result = await run_in_threadpool(
                set_current_version,
                task_id,
                item_id,
                step,
                payload.version,
                source=payload.source,
            )
            return {"result": result, "workspace": _workspace_payload(task_id, item_id)}
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/items/{item_id}/image/star")
    async def post_star_image_version(
        task_id: str,
        item_id: str,
        payload: CandidateStarPayload,
    ) -> dict:
        try:
            item = load_item(task_id, item_id)
            versions = set(item.get("starred_image_versions", []))
            if payload.starred:
                versions.add(payload.version)
            else:
                versions.discard(payload.version)
            await run_in_threadpool(
                update_item_starred_versions,
                task_id,
                item_id,
                sorted(versions, reverse=True),
                source=payload.source,
            )
            return {"workspace": _workspace_payload(task_id, item_id)}
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/items/{item_id}/steps/{step}/approve")
    async def post_approve_step(task_id: str, item_id: str, step: str, payload: StepActionPayload) -> dict:
        try:
            result = await run_in_threadpool(approve_step, task_id, item_id, step, source=payload.source)
            return {"result": result, "workspace": _workspace_payload(task_id, item_id)}
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/items/{item_id}/steps/{step}/rollback")
    async def post_rollback_step(task_id: str, item_id: str, step: str, payload: StepActionPayload) -> dict:
        try:
            result = await run_in_threadpool(rollback_step, task_id, item_id, step, source=payload.source)
            return {"result": result, "workspace": _workspace_payload(task_id, item_id)}
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/items/{item_id}/image/poll")
    async def post_poll_image(task_id: str, item_id: str, payload: ImagePollPayload) -> dict:
        try:
            if payload.version:
                result = await run_in_threadpool(
                    poll_image_generation_version,
                    task_id,
                    item_id,
                    payload.version,
                    source=payload.source,
                )
            else:
                result = await run_in_threadpool(
                    poll_image_generation,
                    task_id,
                    item_id,
                    source=payload.source,
                )
            return {"result": result, "workspace": _workspace_payload(task_id, item_id)}
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/items/{item_id}/image/cancel")
    async def post_cancel_image(task_id: str, item_id: str, payload: StepActionPayload) -> dict:
        try:
            result = await run_in_threadpool(
                cancel_pending_image_generations,
                task_id,
                item_id,
                source=payload.source,
            )
            return {"result": result, "workspace": _workspace_payload(task_id, item_id)}
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/tasks/{task_id}/pipeline/run")
    async def post_run_task_pipeline(task_id: str, payload: TaskPipelinePayload) -> dict:
        try:
            result = await run_in_threadpool(
                run_pipeline,
                task_id,
                auto_approve=payload.auto_approve,
                source=payload.source,
                image_concurrency=payload.image_concurrency or 1,
            )
            return {
                "result": result,
                "task": _task_payload(task_id),
                "items": [_item_summary_payload(task_id, item) for item in list_items(task_id)],
            }
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.patch("/settings/defaults")
    async def patch_settings_defaults(payload: SettingsDefaultsPayload) -> dict:
        settings = load_global_settings()
        defaults = settings.setdefault("defaults", {})
        mappings = [
            ("brief_generation", payload.brief_provider, payload.brief_model),
            ("image_prompt", payload.prompt_provider, payload.prompt_model),
            ("image_generation", payload.image_provider, payload.image_model),
        ]
        for step, provider, model in mappings:
            if provider is not None:
                defaults.setdefault(step, {})
                defaults[step]["provider"] = provider
            if model is not None:
                defaults.setdefault(step, {})
                defaults[step]["model"] = model
        await run_in_threadpool(save_global_settings, settings)
        return _settings_payload()

    @app.patch("/settings/templates")
    async def patch_settings_templates(payload: PromptTemplatesPayload) -> dict:
        await run_in_threadpool(
            update_prompt_templates,
            brief_system_prompt=payload.brief_system_prompt,
            prompt_system_prompt=payload.prompt_system_prompt,
            grid_sheet_prompt_template=payload.grid_sheet_prompt_template,
            grid_sheet_negative_prompt=payload.grid_sheet_negative_prompt,
        )
        return _settings_payload()

    @app.post("/providers")
    async def post_provider(payload: ProviderCreatePayload) -> dict:
        try:
            await run_in_threadpool(
                create_custom_provider,
                label=payload.label,
                provider_type=payload.provider_type,
                base_url=payload.base_url,
                api_key=payload.api_key,
                image_max_concurrency=max(1, payload.image_max_concurrency)
                if payload.image_max_concurrency is not None
                else None,
            )
            return _settings_payload()
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.patch("/providers/{provider_id}")
    async def patch_provider(provider_id: str, payload: ProviderUpdatePayload) -> dict:
        try:
            await run_in_threadpool(
                update_provider_settings,
                provider_id,
                provider_type=payload.provider_type,
                label=payload.label,
                base_url=payload.base_url,
                api_key=payload.api_key,
                image_max_concurrency=max(1, payload.image_max_concurrency)
                if payload.image_max_concurrency is not None
                else None,
            )
            return _settings_payload()
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.delete("/providers/{provider_id}")
    async def delete_provider(provider_id: str) -> dict:
        try:
            await run_in_threadpool(delete_custom_provider, provider_id)
            return _settings_payload()
        except Exception as exc:
            raise _to_http_error(exc) from exc

    @app.post("/providers/{provider_id}/sync-models")
    async def post_provider_sync(provider_id: str) -> dict:
        settings = load_global_settings()
        provider_config = None
        if provider_id in settings.get("providers", {}):
            provider_config = settings["providers"][provider_id]
        else:
            provider_config = next(
                (row for row in settings.get("custom_providers", []) if row.get("id") == provider_id),
                None,
            )
        if provider_config is None:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")
        try:
            models = await run_in_threadpool(
                sync_provider_models,
                provider_id,
                provider_config.get("api_key", ""),
                provider_config,
            )
            await run_in_threadpool(
                update_provider_settings,
                provider_id,
                models=models,
                last_synced_at=utc_now(),
                last_error=None,
            )
            return _settings_payload()
        except Exception as exc:
            await run_in_threadpool(
                update_provider_settings,
                provider_id,
                last_error=str(exc),
            )
            raise _to_http_error(exc) from exc

    return app
