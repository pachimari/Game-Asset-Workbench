from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from .settings import load_global_settings
from .storage import (
    TASKS_DIR,
    item_dir,
    list_artifacts,
    list_items,
    list_tasks,
    load_artifact,
    load_item,
    load_item_chat,
    load_item_events,
    load_task,
)


def _file_url(path: Path) -> str:
    relative = path.relative_to(TASKS_DIR)
    return f"/files/{relative.as_posix()}"


def _candidate_rows(task_id: str, item_id: str) -> dict:
    item = load_item(task_id, item_id)
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
            return load_task(task_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/tasks/{task_id}/items")
    def get_task_items(task_id: str) -> dict:
        try:
            return {"task_id": task_id, "items": list_items(task_id)}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/tasks/{task_id}/items/{item_id}")
    def get_task_item(task_id: str, item_id: str) -> dict:
        try:
            return load_item(task_id, item_id)
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

    return app


app = create_app()
