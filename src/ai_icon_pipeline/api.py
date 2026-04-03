from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

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
from .storage import (
    TASKS_DIR,
    create_item,
    create_task,
    delete_task,
    export_starred_images_zip,
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
    update_item,
    update_item_model_override,
    update_item_starred_versions,
    update_runtime_config,
    update_task_model_override,
    update_task_settings,
)
from .utils import utc_now


class TaskCreatePayload(BaseModel):
    task_name: str
    project_background: str = ""
    style_requirements: str = ""
    asset_domain: str = "game_icon_assets"


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
    api_key: str = ""


class ProviderUpdatePayload(BaseModel):
    label: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None


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


class TaskPipelinePayload(BaseModel):
    auto_approve: bool = True
    source: str = "web"


def _to_http_error(exc: Exception) -> HTTPException:
    message = str(exc)
    status_code = 400
    if "not found" in message.lower():
        status_code = 404
    return HTTPException(status_code=status_code, detail=message)


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


def _download_filename_fragment(value: str) -> str:
    cleaned = value.strip().replace("/", "_").replace("\\", "_")
    cleaned = " ".join(cleaned.split())
    return cleaned[:80] or "batch"


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
    candidate_rows = _candidate_rows(task_id, item["item_id"])
    payload["preview_image_url"] = _item_preview_url(task_id, item["item_id"])
    payload["pending_image_jobs"] = sum(
        1
        for version in candidate_rows.get("versions", [])
        if str((version.get("async_job") or {}).get("status", "")).lower()
        in {"queued", "processing", "pending", "running", "in_progress"}
    )
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
    return task


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
    app.mount("/files", StaticFiles(directory=str(TASKS_DIR)), name="files")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "service": "ai-icon-pipeline-api"}

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
            if payload.image_aspect_ratio is not None or payload.image_resolution is not None:
                await run_in_threadpool(
                    update_runtime_config,
                    task_id,
                    image_aspect_ratio=payload.image_aspect_ratio,
                    image_resolution=payload.image_resolution,
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
            filename = f"{_download_filename_fragment(task.get('task_name', task_id))}_星标图.zip"
            return FileResponse(
                archive_path,
                media_type="application/zip",
                filename=filename,
            )
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


app = create_app()
