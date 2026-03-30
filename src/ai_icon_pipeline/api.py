from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .settings import load_global_settings
from .storage import list_items, list_tasks, load_item, load_task


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

    @app.get("/providers")
    def get_providers() -> dict:
        return {"providers": _provider_rows()}

    return app


app = create_app()
