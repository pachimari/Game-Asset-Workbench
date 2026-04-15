from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import (
    STATUS_ARCHIVED,
    STATUS_BRIEF_APPROVED,
    STATUS_BRIEF_GENERATED,
    STATUS_COMPLETED,
    STATUS_DRAFT,
    STATUS_FAILED,
    STATUS_IMAGE_GENERATED,
    STATUS_IMAGE_GENERATING,
    STATUS_PROMPT_APPROVED,
    STATUS_PROMPT_GENERATED,
    STEP_BRIEF_GENERATION,
    STEP_IMAGE_GENERATION,
    STEP_IMAGE_PROMPT,
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
from .storage import (
    compute_batch_metrics,
    create_item,
    create_task,
    export_starred_images_zip,
    list_artifacts,
    list_items,
    list_tasks,
    load_artifact,
    load_item,
    load_task,
    task_dir,
    update_item,
    update_item_starred_versions,
    update_runtime_config,
    update_task_settings,
)
from .providers.registry import ProviderRequestError
from .providers.registry import sync_provider_models
from .state_machine import APPROVAL_RULES, GENERATION_RULES, StateMachineError
from .settings import (
    UNSET,
    create_custom_provider,
    delete_custom_provider,
    load_global_settings,
    provider_settings_for,
    resolve_stage_selection,
    set_global_default,
    update_provider_settings,
)


STEP_CHOICES = [STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT, STEP_IMAGE_GENERATION]
ASYNC_STEPS = [STEP_IMAGE_GENERATION]
STATUS_CHOICES = [
    STATUS_DRAFT,
    STATUS_BRIEF_GENERATED,
    STATUS_BRIEF_APPROVED,
    STATUS_PROMPT_GENERATED,
    STATUS_PROMPT_APPROVED,
    STATUS_IMAGE_GENERATING,
    STATUS_IMAGE_GENERATED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_ARCHIVED,
]
COMMAND_SPECS = {
    "create-task": {
        "group": "task",
        "description": "Create a batch task",
        "args": ["--task-name", "--project-background", "--style-requirements", "--asset-domain", "--task-id", "--input-file"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["ok", "action", "task_id", "task_dir"]},
        "errors": ["TASK_ALREADY_EXISTS", "VALIDATION_ERROR"],
    },
    "create-item": {
        "group": "item",
        "description": "Create one item inside a task",
        "args": ["task_id", "--item-id", "--asset-type", "--title", "--description", "--category", "--extra-context"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["item_id", "asset_type", "title", "description", "status", "current_versions"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_ALREADY_EXISTS", "VALIDATION_ERROR"],
    },
    "update-item": {
        "group": "item",
        "description": "Update one item source payload",
        "args": ["task_id", "item_id", "--asset-type", "--title", "--description", "--category", "--extra-context"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["item_id", "asset_type", "title", "description", "status", "current_versions"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND", "VALIDATION_ERROR"],
    },
    "run-step": {
        "group": "step",
        "description": "Run a single step for one item",
        "args": ["task_id", "item_id", "step"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["task_id", "item_id", "step", "status", "version"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND", "STATE_TRANSITION_INVALID", "PROVIDER_REQUEST_FAILED"],
    },
    "approve-step": {
        "group": "step",
        "description": "Approve one generated step",
        "args": ["task_id", "[item_id]", "step", "--all-items"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["task_id", "item_id", "step", "status", "current_versions"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND", "STATE_TRANSITION_INVALID"],
    },
    "run-pipeline": {
        "group": "pipeline",
        "description": "Run a task or one item end-to-end",
        "args": ["task_id", "--item-id", "--no-auto-approve", "--stop-at", "--parallel", "--image-concurrency", "--delay"],
        "supports_json": True,
        "output": {"type": "object"},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND", "STATE_TRANSITION_INVALID", "PROVIDER_REQUEST_FAILED"],
    },
    "show-task": {
        "group": "task",
        "description": "Show current task snapshot",
        "args": ["task_id"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["task_id", "task_name", "status", "items", "items_summary"]},
        "errors": ["TASK_NOT_FOUND"],
    },
    "list-tasks": {
        "group": "task",
        "description": "List tasks",
        "args": [],
        "supports_json": True,
        "output": {"type": "array"},
        "errors": [],
    },
    "update-task": {
        "group": "task",
        "description": "Update task-level settings and image defaults",
        "args": [
            "task_id",
            "--task-name",
            "--project-background",
            "--style-requirements",
            "--asset-domain",
            "--image-aspect-ratio",
            "--image-resolution",
        ],
        "supports_json": True,
        "output": {"type": "object", "keys": ["task_id", "task_name", "project_background", "style_requirements", "asset_domain"]},
        "errors": ["TASK_NOT_FOUND", "VALIDATION_ERROR"],
    },
    "task-metrics": {
        "group": "task",
        "description": "Show batch workflow metrics",
        "args": ["task_id"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["generated_items", "total_redos", "starred_images", "failure_counts"]},
        "errors": ["TASK_NOT_FOUND"],
    },
    "list-items": {
        "group": "item",
        "description": "List items in a task",
        "args": ["task_id"],
        "supports_json": True,
        "output": {"type": "array"},
        "errors": ["TASK_NOT_FOUND"],
    },
    "show-item": {
        "group": "item",
        "description": "Show one item snapshot",
        "args": ["task_id", "item_id"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["item_id", "status", "current_versions", "model_overrides", "runtime_overrides"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND"],
    },
    "list-artifacts": {
        "group": "artifact",
        "description": "List artifact versions for one step or all steps",
        "args": ["task_id", "item_id", "[step]"],
        "supports_json": True,
        "output": {"type": "array"},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND"],
    },
    "show-artifact": {
        "group": "artifact",
        "description": "Show one artifact payload",
        "args": ["task_id", "item_id", "step", "version"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["step", "provider", "model", "created_at", "input", "output"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND", "ARTIFACT_NOT_FOUND"],
    },
    "edit-brief": {
        "group": "brief",
        "description": "Create a manual brief version",
        "args": ["task_id", "item_id", "--title", "--description", "--keywords", "--icon-subject", "--visual-focus", "--note"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["task_id", "item_id", "step", "version", "status"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND", "VALIDATION_ERROR"],
    },
    "edit-prompt": {
        "group": "prompt",
        "description": "Create a manual prompt version",
        "args": ["task_id", "item_id", "--prompt", "--negative-prompt", "--note"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["task_id", "item_id", "step", "version", "status"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND", "VALIDATION_ERROR"],
    },
    "set-current-version": {
        "group": "artifact",
        "description": "Switch the active version for one step",
        "args": ["task_id", "item_id", "step", "version"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["task_id", "item_id", "step", "version", "status"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND", "ARTIFACT_NOT_FOUND"],
    },
    "rollback-step": {
        "group": "step",
        "description": "Move an item back to a previous stage",
        "args": ["task_id", "[item_id]", "step", "--all-items"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["task_id", "item_id", "step", "status", "current_versions"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND", "ARTIFACT_NOT_FOUND", "VALIDATION_ERROR"],
    },
    "capabilities": {
        "group": "agent",
        "description": "Show discoverable CLI capabilities",
        "args": ["--verbose"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["supports_json", "commands"]},
        "errors": [],
    },
    "schema": {
        "group": "agent",
        "description": "Show machine-readable schemas",
        "args": ["command", "state-machine"],
        "supports_json": True,
        "output": {"type": "object"},
        "errors": [],
    },
    "workflow-help": {
        "group": "agent",
        "description": "Show recommended workflows",
        "args": [],
        "supports_json": True,
        "output": {"type": "object", "keys": ["workflows"]},
        "errors": [],
    },
    "available-actions": {
        "group": "agent",
        "description": "Show recommended next actions for one item",
        "args": ["task_id", "item_id"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["status", "available_actions"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND"],
    },
    "provider-list": {
        "group": "provider",
        "description": "List configured providers",
        "args": [],
        "supports_json": True,
        "output": {"type": "array"},
        "errors": [],
    },
    "provider-show": {
        "group": "provider",
        "description": "Show one provider config",
        "args": ["provider_id"],
        "supports_json": True,
        "output": {"type": "object"},
        "errors": ["PROVIDER_NOT_FOUND"],
    },
    "provider-add": {
        "group": "provider",
        "description": "Add one custom provider",
        "args": ["--label", "--provider-type", "--base-url", "--api-key", "--image-max-concurrency"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["providers", "custom_providers"]},
        "errors": ["VALIDATION_ERROR"],
    },
    "provider-update": {
        "group": "provider",
        "description": "Update one provider config",
        "args": ["provider_id", "--label", "--provider-type", "--base-url", "--api-key", "--image-max-concurrency"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["providers", "custom_providers"]},
        "errors": ["PROVIDER_NOT_FOUND", "VALIDATION_ERROR"],
    },
    "provider-delete": {
        "group": "provider",
        "description": "Delete one custom provider",
        "args": ["provider_id"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["providers", "custom_providers"]},
        "errors": ["PROVIDER_NOT_FOUND"],
    },
    "provider-sync-models": {
        "group": "provider",
        "description": "Sync models for one provider",
        "args": ["provider_id"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["provider_id", "model_count", "models"]},
        "errors": ["PROVIDER_NOT_FOUND", "PROVIDER_REQUEST_FAILED", "VALIDATION_ERROR"],
    },
    "provider-set-default": {
        "group": "provider",
        "description": "Set the global default provider/model for one step",
        "args": ["--step", "--provider", "--model"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["step", "provider", "model", "source"]},
        "errors": ["VALIDATION_ERROR"],
    },
    "image-pending": {
        "group": "image",
        "description": "List pending async image jobs for one item",
        "args": ["task_id", "item_id"],
        "supports_json": True,
        "output": {"type": "array"},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND"],
    },
    "image-poll": {
        "group": "image",
        "description": "Poll current or specified async image job",
        "args": ["task_id", "item_id", "--version"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["task_id", "item_id", "step", "version", "status"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND", "ARTIFACT_NOT_FOUND", "VALIDATION_ERROR", "PROVIDER_REQUEST_FAILED"],
    },
    "image-cancel": {
        "group": "image",
        "description": "Cancel local waiting for pending image jobs",
        "args": ["task_id", "item_id"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["task_id", "item_id", "cancelled_versions", "status", "current_version"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND", "VALIDATION_ERROR"],
    },
    "image-star": {
        "group": "image",
        "description": "Add one image generation version to the starred set",
        "args": ["task_id", "item_id", "version"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["item_id", "starred_image_versions"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND"],
    },
    "image-unstar": {
        "group": "image",
        "description": "Remove one image generation version from the starred set",
        "args": ["task_id", "item_id", "version"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["item_id", "starred_image_versions"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND"],
    },
    "image-starred": {
        "group": "image",
        "description": "List starred image versions in one task",
        "args": ["task_id"],
        "supports_json": True,
        "output": {"type": "array"},
        "errors": ["TASK_NOT_FOUND"],
    },
    "export-starred": {
        "group": "export",
        "description": "Export all starred images in a task as a ZIP file",
        "args": ["task_id"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["task_id", "archive_path"]},
        "errors": ["TASK_NOT_FOUND", "VALIDATION_ERROR"],
    },
    "runtime-resolve": {
        "group": "runtime",
        "description": "Resolve effective provider/model for one item step",
        "args": ["task_id", "item_id", "--step"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["task_id", "item_id", "step", "provider", "model", "source"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND", "VALIDATION_ERROR"],
    },
}
COMMAND_ALIASES = {
    "task.create": "create-task",
    "task.list": "list-tasks",
    "task.show": "show-task",
    "task.update": "update-task",
    "task.metrics": "task-metrics",
    "item.create": "create-item",
    "item.update": "update-item",
    "item.list": "list-items",
    "item.show": "show-item",
    "item.actions": "available-actions",
    "step.run": "run-step",
    "step.approve": "approve-step",
    "step.rollback": "rollback-step",
    "pipeline.run": "run-pipeline",
    "artifact.list": "list-artifacts",
    "artifact.show": "show-artifact",
    "artifact.use": "set-current-version",
    "brief.edit": "edit-brief",
    "prompt.edit": "edit-prompt",
    "agent.capabilities": "capabilities",
    "agent.workflow-help": "workflow-help",
    "provider.list": "provider-list",
    "provider.show": "provider-show",
    "provider.add": "provider-add",
    "provider.update": "provider-update",
    "provider.delete": "provider-delete",
    "provider.sync-models": "provider-sync-models",
    "provider.set-default": "provider-set-default",
    "image.pending": "image-pending",
    "image.poll": "image-poll",
    "image.cancel": "image-cancel",
    "image.star": "image-star",
    "image.unstar": "image-unstar",
    "image.starred": "image-starred",
    "export.starred": "export-starred",
    "runtime.resolve": "runtime-resolve",
}


def _load_task_payload(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_keywords(raw_keywords: str | None) -> list[str] | None:
    if raw_keywords is None:
        return None
    return [keyword.strip() for keyword in raw_keywords.split(",") if keyword.strip()]


def _emit(data, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if isinstance(data, (dict, list)):
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    print(str(data))


def _error_code_for(exc: Exception) -> str:
    message = str(exc)
    if isinstance(exc, StateMachineError):
        return "STATE_TRANSITION_INVALID"
    if isinstance(exc, ProviderRequestError):
        return "PROVIDER_REQUEST_FAILED"
    if message.startswith("Task not found:"):
        return "TASK_NOT_FOUND"
    if message.startswith("Item not found:"):
        return "ITEM_NOT_FOUND"
    if message.startswith("Artifact not found:"):
        return "ARTIFACT_NOT_FOUND"
    if message.startswith("Task already exists:"):
        return "TASK_ALREADY_EXISTS"
    if message.startswith("Item already exists:"):
        return "ITEM_ALREADY_EXISTS"
    if message.startswith("Unsupported provider:") or message.startswith("Unsupported native image provider:") or message.startswith("Unsupported async image provider:"):
        return "PROVIDER_NOT_FOUND"
    if message.startswith("Unsupported step:") or message.startswith("非法步骤："):
        return "STEP_INVALID"
    return "VALIDATION_ERROR" if isinstance(exc, ValueError) else "INTERNAL_ERROR"


def _emit_error(exc: Exception, *, as_json: bool) -> int:
    payload = {
        "ok": False,
        "error_code": _error_code_for(exc),
        "message": str(exc),
    }
    _emit(payload, as_json=as_json)
    return 1


def _command_schema(command_name: str) -> dict:
    canonical_name = COMMAND_ALIASES.get(command_name, command_name)
    spec = COMMAND_SPECS[canonical_name]
    payload = {
        "command": command_name,
        "canonical_command": canonical_name,
        "group": spec["group"],
        "description": spec["description"],
        "args": spec["args"],
        "supports_json": spec["supports_json"],
        "output": spec.get("output", {}),
        "errors": spec.get("errors", []),
    }
    if canonical_name != command_name:
        payload["alias_of"] = canonical_name
    aliases = sorted(alias for alias, target in COMMAND_ALIASES.items() if target == canonical_name)
    if aliases:
        payload["aliases"] = aliases
    return payload


def _state_machine_schema() -> dict:
    return {
        "statuses": STATUS_CHOICES,
        "async_steps": {
            STEP_IMAGE_GENERATION: {
                "run_returns": STATUS_IMAGE_GENERATING,
                "completion_status": STATUS_IMAGE_GENERATED,
                "poll_command": "image-poll",
                "cancel_command": "image-cancel",
            }
        },
        "generation_rules": {
            step: {
                "allowed_statuses": sorted(rule["allowed_statuses"]),
                "next_status": rule["next_status"],
                "async": step in ASYNC_STEPS,
            }
            for step, rule in GENERATION_RULES.items()
        },
        "approval_rules": {
            step: {
                "required_status": rule["required_status"],
                "next_status": rule["next_status"],
            }
            for step, rule in APPROVAL_RULES.items()
        },
    }


def _workflow_help() -> dict:
    return {
        "workflows": [
            {
                "name": "single_item_happy_path",
                "steps": [
                    "create-task",
                    "create-item",
                    "run-step brief_generation",
                    "approve-step brief_generation",
                    "run-step image_prompt",
                    "approve-step image_prompt",
                    "run-step image_generation",
                    "image-poll (repeat until image_generated)",
                    "approve-step image_generation",
                ],
                "notes": [
                    "image_generation 是异步步骤。",
                    "run-step image_generation 返回 image_generating 后，需要继续调用 image-poll。",
                ],
            },
            {
                "name": "single_item_manual_review",
                "steps": [
                    "run-step brief_generation",
                    "edit-brief",
                    "approve-step brief_generation",
                    "run-step image_prompt",
                    "edit-prompt",
                    "approve-step image_prompt",
                    "run-step image_generation",
                ],
                "notes": [
                    "如果 image_generation 进入 image_generating，需要继续调用 image-poll。",
                ],
            },
            {
                "name": "image_retry_after_failure",
                "steps": [
                    "show-item",
                    "run-step image_generation",
                    "rollback-step image_prompt",
                    "run-step image_prompt",
                    "approve-step image_prompt",
                    "run-step image_generation",
                ],
                "notes": [
                    "失败后可以直接重跑 image_generation，也可以先回退到出图指令。",
                ],
            },
            {
                "name": "run_pipeline_vs_manual",
                "steps": [
                    "run-pipeline",
                    "run-pipeline --no-auto-approve",
                ],
                "notes": [
                    "run-pipeline 会自动串起多步主流程。",
                    "--no-auto-approve 适合人工审核为主的流程。",
                    "如果走到异步图片阶段，后续仍然需要 image-poll 或 UI 自动轮询。",
                ],
            },
        ]
    }


def _list_provider_entries() -> list[dict]:
    settings = load_global_settings()
    rows = []
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


def _load_provider_config(provider_id: str) -> dict:
    settings = load_global_settings()
    config = provider_settings_for(settings, provider_id)
    if not config:
        raise ValueError(f"Unsupported provider: {provider_id}")
    payload = dict(config)
    payload["id"] = provider_id
    if payload.get("api_key"):
        raw = str(payload["api_key"])
        if len(raw) <= 8:
            payload["api_key"] = "*" * len(raw)
        else:
            payload["api_key"] = f"{raw[:4]}...{raw[-4:]}"
    return payload


def _pending_image_jobs(task_id: str, item_id: str) -> list[dict]:
    rows = []
    for artifact_meta in list_artifacts(task_id, item_id, STEP_IMAGE_GENERATION):
        version = artifact_meta["version"]
        artifact = load_artifact(task_id, item_id, STEP_IMAGE_GENERATION, version)
        async_job = artifact.get("async_job", {})
        status = str(async_job.get("status", "")).lower()
        if status in {"queued", "processing", "pending", "running", "in_progress"}:
            rows.append(
                {
                    "version": version,
                    "provider": artifact.get("provider"),
                    "model": artifact.get("model"),
                    "task_id": async_job.get("task_id"),
                    "status": async_job.get("status"),
                    "progress": async_job.get("progress", 0),
                    "updated_at": async_job.get("updated_at"),
                }
            )
    return rows


def _starred_image_versions(task_id: str) -> list[dict]:
    rows = []
    for item in list_items(task_id):
        for version in item.get("starred_image_versions", []):
            rows.append(
                {
                    "task_id": task_id,
                    "item_id": item["item_id"],
                    "title": item.get("title", ""),
                    "version": version,
                    "is_current": item.get("current_versions", {}).get(STEP_IMAGE_GENERATION) == version,
                }
            )
    return rows


def _set_starred_image_version(task_id: str, item_id: str, version: str, *, starred: bool) -> dict:
    item = load_item(task_id, item_id)
    available_versions = {
        artifact_meta["version"] for artifact_meta in list_artifacts(task_id, item_id, STEP_IMAGE_GENERATION)
    }
    if version not in available_versions:
        raise ValueError(f"Image version not found: {version}")
    versions = list(dict.fromkeys(item.get("starred_image_versions", [])))
    if starred and version not in versions:
        versions.append(version)
    if not starred:
        versions = [current for current in versions if current != version]
    return update_item_starred_versions(task_id, item_id, versions, source="cli")


def _runtime_resolution(task_id: str, item_id: str, step: str) -> dict:
    task = load_task(task_id)
    item = load_item(task_id, item_id)
    settings = load_global_settings()
    selection = resolve_stage_selection(task, item, settings, step)
    return {
        "task_id": task_id,
        "item_id": item_id,
        "step": step,
        **selection,
    }


def _list_artifacts_any(task_id: str, item_id: str, step: str | None) -> list[dict]:
    if step:
        return list_artifacts(task_id, item_id, step)
    rows = []
    for current_step in STEP_CHOICES:
        rows.extend(list_artifacts(task_id, item_id, current_step))
    rows.sort(key=lambda row: (row["step"], row["version"], row["manual"]))
    return rows


def _available_actions(task_id: str, item_id: str) -> dict:
    item = load_item(task_id, item_id)
    status = item.get("status", STATUS_DRAFT)
    actions: list[dict] = []
    if status == STATUS_DRAFT:
        actions.append({"command": "run-step", "step": STEP_BRIEF_GENERATION})
    elif status == STATUS_BRIEF_GENERATED:
        actions.extend([
            {"command": "approve-step", "step": STEP_BRIEF_GENERATION},
            {"command": "run-step", "step": STEP_BRIEF_GENERATION},
            {"command": "edit-brief"},
        ])
    elif status == STATUS_BRIEF_APPROVED:
        actions.extend([
            {"command": "run-step", "step": STEP_IMAGE_PROMPT},
            {"command": "rollback-step", "step": STEP_BRIEF_GENERATION},
        ])
    elif status == STATUS_PROMPT_GENERATED:
        actions.extend([
            {"command": "approve-step", "step": STEP_IMAGE_PROMPT},
            {"command": "run-step", "step": STEP_IMAGE_PROMPT},
            {"command": "edit-prompt"},
        ])
    elif status == STATUS_PROMPT_APPROVED:
        actions.extend([
            {"command": "run-step", "step": STEP_IMAGE_GENERATION, "async": True},
            {"command": "rollback-step", "step": STEP_IMAGE_PROMPT},
        ])
    elif status == STATUS_IMAGE_GENERATING:
        actions.extend([
            {"command": "image-poll"},
            {"command": "image-cancel"},
            {"command": "run-step", "step": STEP_IMAGE_GENERATION, "async": True},
        ])
    elif status == STATUS_IMAGE_GENERATED:
        actions.extend([
            {"command": "approve-step", "step": STEP_IMAGE_GENERATION},
            {"command": "run-step", "step": STEP_IMAGE_GENERATION, "async": True},
            {"command": "set-current-version", "step": STEP_IMAGE_GENERATION},
        ])
    elif status == STATUS_FAILED:
        actions.extend([
            {"command": "run-step", "step": STEP_IMAGE_GENERATION, "async": True},
            {"command": "rollback-step", "step": STEP_IMAGE_PROMPT},
        ])
    return {"status": status, "available_actions": actions}


def _bulk_step_action(
    task_id: str,
    *,
    step: str,
    action: str,
) -> dict:
    results = []
    skipped = []
    for item in list_items(task_id):
        current_item_id = item["item_id"]
        try:
            if action == "approve":
                results.append(approve_step(task_id, current_item_id, step))
            elif action == "rollback":
                results.append(rollback_step(task_id, current_item_id, step))
            else:  # pragma: no cover - defensive
                raise ValueError(f"Unsupported bulk action: {action}")
        except (StateMachineError, ValueError) as exc:
            skipped.append(
                {
                    "item_id": current_item_id,
                    "status": item.get("status"),
                    "reason": str(exc),
                }
            )
    return {
        "task_id": task_id,
        "step": step,
        "action": action,
        "updated_count": len(results),
        "results": results,
        "skipped": skipped,
    }


def _normalize_step_target(args: argparse.Namespace) -> tuple[str | None, str]:
    item_id = args.item_id
    step = args.step
    if args.all_items and step is None and item_id in STEP_CHOICES:
        step = item_id
        item_id = None
    if not step:
        raise ValueError("step is required")
    return item_id, step


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-icon-pipeline")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-task", help="Create a batch task", parents=[common_parser])
    create.add_argument("--task-name", default="Untitled icon batch")
    create.add_argument("--project-background", default="")
    create.add_argument("--style-requirements", default="")
    create.add_argument("--asset-domain", default="game_icon_assets")
    create.add_argument("--task-id")
    create.add_argument("--input-file", help="JSON file containing task metadata and optional items")

    create_item_parser = subparsers.add_parser("create-item", help="Create one item inside a task", parents=[common_parser])
    create_item_parser.add_argument("task_id")
    create_item_parser.add_argument("--item-id")
    create_item_parser.add_argument("--asset-type", default="generic_icon")
    create_item_parser.add_argument("--title", default="")
    create_item_parser.add_argument("--description", default="")
    create_item_parser.add_argument("--category", default="")
    create_item_parser.add_argument("--extra-context", default="")

    update_item_parser = subparsers.add_parser("update-item", help="Update one item source payload", parents=[common_parser])
    update_item_parser.add_argument("task_id")
    update_item_parser.add_argument("item_id")
    update_item_parser.add_argument("--asset-type")
    update_item_parser.add_argument("--title")
    update_item_parser.add_argument("--description")
    update_item_parser.add_argument("--category")
    update_item_parser.add_argument("--extra-context")

    run_single = subparsers.add_parser("run-step", help="Run a single step for one item", parents=[common_parser])
    run_single.add_argument("task_id")
    run_single.add_argument("item_id")
    run_single.add_argument("step", choices=STEP_CHOICES)

    approve = subparsers.add_parser("approve-step", help="Approve one generated step", parents=[common_parser])
    approve.add_argument("task_id")
    approve.add_argument("item_id", nargs="?")
    approve.add_argument("step", nargs="?", choices=STEP_CHOICES)
    approve.add_argument("--all-items", action="store_true")

    run_all = subparsers.add_parser("run-pipeline", help="Run a task or one item end-to-end", parents=[common_parser])
    run_all.add_argument("task_id")
    run_all.add_argument("--item-id")
    run_all.add_argument(
        "--no-auto-approve",
        action="store_true",
        help="Stop after each generated step instead of auto-approving it",
    )
    run_all.add_argument("--stop-at", choices=STATUS_CHOICES)
    run_all.add_argument("--parallel", type=int, default=1)
    run_all.add_argument(
        "--image-concurrency",
        type=int,
        default=1,
        help="Batch-level image generation concurrency. Actual provider submission still respects each provider limit.",
    )
    run_all.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Delay in seconds between batch item submissions",
    )

    show = subparsers.add_parser("show-task", help="Show current task snapshot", parents=[common_parser])
    show.add_argument("task_id")
    list_tasks_parser = subparsers.add_parser("list-tasks", help="List tasks", parents=[common_parser])
    update_task_parser = subparsers.add_parser("update-task", help="Update task-level settings", parents=[common_parser])
    update_task_parser.add_argument("task_id")
    update_task_parser.add_argument("--task-name")
    update_task_parser.add_argument("--project-background")
    update_task_parser.add_argument("--style-requirements")
    update_task_parser.add_argument("--asset-domain")
    update_task_parser.add_argument("--image-aspect-ratio")
    update_task_parser.add_argument("--image-resolution")
    task_metrics_parser = subparsers.add_parser("task-metrics", help="Show batch workflow metrics", parents=[common_parser])
    task_metrics_parser.add_argument("task_id")

    list_items_parser = subparsers.add_parser("list-items", help="List items in a task", parents=[common_parser])
    list_items_parser.add_argument("task_id")

    show_item = subparsers.add_parser("show-item", help="Show one item snapshot", parents=[common_parser])
    show_item.add_argument("task_id")
    show_item.add_argument("item_id")

    list_artifacts_parser = subparsers.add_parser(
        "list-artifacts", help="List artifact versions for one step or all steps", parents=[common_parser]
    )
    list_artifacts_parser.add_argument("task_id")
    list_artifacts_parser.add_argument("item_id")
    list_artifacts_parser.add_argument("step", nargs="?", choices=STEP_CHOICES)

    show_artifact_parser = subparsers.add_parser(
        "show-artifact", help="Show one artifact payload", parents=[common_parser]
    )
    show_artifact_parser.add_argument("task_id")
    show_artifact_parser.add_argument("item_id")
    show_artifact_parser.add_argument("step", choices=STEP_CHOICES)
    show_artifact_parser.add_argument("version")

    edit_brief_parser = subparsers.add_parser("edit-brief", help="Create a manual brief version", parents=[common_parser])
    edit_brief_parser.add_argument("task_id")
    edit_brief_parser.add_argument("item_id")
    edit_brief_parser.add_argument("--title")
    edit_brief_parser.add_argument("--description")
    edit_brief_parser.add_argument("--keywords")
    edit_brief_parser.add_argument("--icon-subject")
    edit_brief_parser.add_argument("--visual-focus")
    edit_brief_parser.add_argument("--note")

    edit_prompt_parser = subparsers.add_parser("edit-prompt", help="Create a manual prompt version", parents=[common_parser])
    edit_prompt_parser.add_argument("task_id")
    edit_prompt_parser.add_argument("item_id")
    edit_prompt_parser.add_argument("--prompt")
    edit_prompt_parser.add_argument("--negative-prompt")
    edit_prompt_parser.add_argument("--note")

    set_current_parser = subparsers.add_parser(
        "set-current-version", help="Switch the active version for one step", parents=[common_parser]
    )
    set_current_parser.add_argument("task_id")
    set_current_parser.add_argument("item_id")
    set_current_parser.add_argument("step", choices=STEP_CHOICES)
    set_current_parser.add_argument("version")

    rollback_parser = subparsers.add_parser(
        "rollback-step", help="Move an item back to a previous stage using the latest version there", parents=[common_parser]
    )
    rollback_parser.add_argument("task_id")
    rollback_parser.add_argument("item_id", nargs="?")
    rollback_parser.add_argument("step", nargs="?", choices=[STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT])
    rollback_parser.add_argument("--all-items", action="store_true")

    capabilities = subparsers.add_parser("capabilities", help="Show discoverable CLI capabilities", parents=[common_parser])
    capabilities.add_argument("--verbose", action="store_true")

    schema = subparsers.add_parser("schema", help="Show machine-readable schemas", parents=[common_parser])
    schema_subparsers = schema.add_subparsers(dest="schema_command", required=True)
    schema_command = schema_subparsers.add_parser("command", help="Show one command schema", parents=[common_parser])
    schema_command.add_argument("name", choices=sorted({*COMMAND_SPECS, *COMMAND_ALIASES}))
    schema_subparsers.add_parser("state-machine", help="Show state machine schema", parents=[common_parser])

    workflow_help = subparsers.add_parser("workflow-help", help="Show recommended workflows", parents=[common_parser])
    workflow_help.add_argument("--name", choices=["single_item_happy_path", "single_item_manual_review", "image_retry_after_failure", "run_pipeline_vs_manual"])
    available_actions = subparsers.add_parser("available-actions", help="Show recommended next actions for one item", parents=[common_parser])
    available_actions.add_argument("task_id")
    available_actions.add_argument("item_id")

    provider_list = subparsers.add_parser("provider-list", help="List configured providers", parents=[common_parser])
    provider_show = subparsers.add_parser("provider-show", help="Show one provider config", parents=[common_parser])
    provider_show.add_argument("provider_id")
    provider_add = subparsers.add_parser("provider-add", help="Add one custom provider", parents=[common_parser])
    provider_add.add_argument("--label", required=True)
    provider_add.add_argument("--provider-type", required=True, choices=["openai_compatible", "async_image", "gemini_native"])
    provider_add.add_argument("--base-url", required=True)
    provider_add.add_argument("--api-key", default="")
    provider_add.add_argument("--image-max-concurrency", type=int)
    provider_update = subparsers.add_parser("provider-update", help="Update one provider config", parents=[common_parser])
    provider_update.add_argument("provider_id")
    provider_update.add_argument("--label")
    provider_update.add_argument("--provider-type", choices=["openai_compatible", "async_image", "gemini_native"])
    provider_update.add_argument("--base-url")
    provider_update.add_argument("--api-key")
    provider_update.add_argument("--image-max-concurrency", type=int)
    provider_delete = subparsers.add_parser("provider-delete", help="Delete one custom provider", parents=[common_parser])
    provider_delete.add_argument("provider_id")
    provider_sync = subparsers.add_parser("provider-sync-models", help="Sync models for one provider", parents=[common_parser])
    provider_sync.add_argument("provider_id")
    provider_set_default = subparsers.add_parser(
        "provider-set-default",
        help="Set the global default provider/model for one step",
        parents=[common_parser],
    )
    provider_set_default.add_argument("--step", required=True, choices=STEP_CHOICES)
    provider_set_default.add_argument("--provider", required=True)
    provider_set_default.add_argument("--model", required=True)

    image_pending = subparsers.add_parser("image-pending", help="List pending async image jobs", parents=[common_parser])
    image_pending.add_argument("task_id")
    image_pending.add_argument("item_id")
    image_poll = subparsers.add_parser("image-poll", help="Poll async image generation", parents=[common_parser])
    image_poll.add_argument("task_id")
    image_poll.add_argument("item_id")
    image_poll.add_argument("--version")
    image_cancel = subparsers.add_parser("image-cancel", help="Cancel local waiting for pending image jobs", parents=[common_parser])
    image_cancel.add_argument("task_id")
    image_cancel.add_argument("item_id")
    image_star = subparsers.add_parser("image-star", help="Add one image version to the starred set", parents=[common_parser])
    image_star.add_argument("task_id")
    image_star.add_argument("item_id")
    image_star.add_argument("version")
    image_unstar = subparsers.add_parser("image-unstar", help="Remove one image version from the starred set", parents=[common_parser])
    image_unstar.add_argument("task_id")
    image_unstar.add_argument("item_id")
    image_unstar.add_argument("version")
    image_starred = subparsers.add_parser("image-starred", help="List starred image versions in one task", parents=[common_parser])
    image_starred.add_argument("task_id")
    export_starred = subparsers.add_parser("export-starred", help="Export all starred images in a task", parents=[common_parser])
    export_starred.add_argument("task_id")
    runtime_resolve = subparsers.add_parser("runtime-resolve", help="Resolve effective runtime for one item step", parents=[common_parser])
    runtime_resolve.add_argument("task_id")
    runtime_resolve.add_argument("item_id")
    runtime_resolve.add_argument("--step", required=True, choices=STEP_CHOICES)

    task_group = subparsers.add_parser("task", help="Task-scoped commands", parents=[common_parser])
    task_subparsers = task_group.add_subparsers(dest="task_command", required=True)
    task_create = task_subparsers.add_parser("create", help="Create a batch task", parents=[common_parser])
    task_create.set_defaults(command="create-task")
    task_create.add_argument("--task-name", default="Untitled icon batch")
    task_create.add_argument("--project-background", default="")
    task_create.add_argument("--style-requirements", default="")
    task_create.add_argument("--asset-domain", default="game_icon_assets")
    task_create.add_argument("--task-id")
    task_create.add_argument("--input-file", help="JSON file containing task metadata and optional items")
    task_show = task_subparsers.add_parser("show", help="Show current task snapshot", parents=[common_parser])
    task_show.set_defaults(command="show-task")
    task_show.add_argument("task_id")
    task_list = task_subparsers.add_parser("list", help="List tasks", parents=[common_parser])
    task_list.set_defaults(command="list-tasks")
    task_update = task_subparsers.add_parser("update", help="Update task-level settings", parents=[common_parser])
    task_update.set_defaults(command="update-task")
    task_update.add_argument("task_id")
    task_update.add_argument("--task-name")
    task_update.add_argument("--project-background")
    task_update.add_argument("--style-requirements")
    task_update.add_argument("--asset-domain")
    task_update.add_argument("--image-aspect-ratio")
    task_update.add_argument("--image-resolution")
    task_metrics = task_subparsers.add_parser("metrics", help="Show batch workflow metrics", parents=[common_parser])
    task_metrics.set_defaults(command="task-metrics")
    task_metrics.add_argument("task_id")

    item_group = subparsers.add_parser("item", help="Item-scoped commands", parents=[common_parser])
    item_subparsers = item_group.add_subparsers(dest="item_command", required=True)
    item_create = item_subparsers.add_parser("create", help="Create one item inside a task", parents=[common_parser])
    item_create.set_defaults(command="create-item")
    item_create.add_argument("task_id")
    item_create.add_argument("--item-id")
    item_create.add_argument("--asset-type", default="generic_icon")
    item_create.add_argument("--title", default="")
    item_create.add_argument("--description", default="")
    item_create.add_argument("--category", default="")
    item_create.add_argument("--extra-context", default="")
    item_update = item_subparsers.add_parser("update", help="Update one item source payload", parents=[common_parser])
    item_update.set_defaults(command="update-item")
    item_update.add_argument("task_id")
    item_update.add_argument("item_id")
    item_update.add_argument("--asset-type")
    item_update.add_argument("--title")
    item_update.add_argument("--description")
    item_update.add_argument("--category")
    item_update.add_argument("--extra-context")
    item_list = item_subparsers.add_parser("list", help="List items in a task", parents=[common_parser])
    item_list.set_defaults(command="list-items")
    item_list.add_argument("task_id")
    item_show = item_subparsers.add_parser("show", help="Show one item snapshot", parents=[common_parser])
    item_show.set_defaults(command="show-item")
    item_show.add_argument("task_id")
    item_show.add_argument("item_id")
    item_actions = item_subparsers.add_parser("actions", help="Show recommended next actions for one item", parents=[common_parser])
    item_actions.set_defaults(command="available-actions")
    item_actions.add_argument("task_id")
    item_actions.add_argument("item_id")

    step_group = subparsers.add_parser("step", help="Step execution commands", parents=[common_parser])
    step_subparsers = step_group.add_subparsers(dest="step_command", required=True)
    step_run = step_subparsers.add_parser("run", help="Run a single step for one item", parents=[common_parser])
    step_run.set_defaults(command="run-step")
    step_run.add_argument("task_id")
    step_run.add_argument("item_id")
    step_run.add_argument("step", choices=STEP_CHOICES)
    step_approve = step_subparsers.add_parser("approve", help="Approve one generated step", parents=[common_parser])
    step_approve.set_defaults(command="approve-step")
    step_approve.add_argument("task_id")
    step_approve.add_argument("item_id", nargs="?")
    step_approve.add_argument("step", nargs="?", choices=STEP_CHOICES)
    step_approve.add_argument("--all-items", action="store_true")
    step_rollback = step_subparsers.add_parser("rollback", help="Move an item back to a previous stage", parents=[common_parser])
    step_rollback.set_defaults(command="rollback-step")
    step_rollback.add_argument("task_id")
    step_rollback.add_argument("item_id", nargs="?")
    step_rollback.add_argument("step", nargs="?", choices=[STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT])
    step_rollback.add_argument("--all-items", action="store_true")

    artifact_group = subparsers.add_parser("artifact", help="Artifact version commands", parents=[common_parser])
    artifact_subparsers = artifact_group.add_subparsers(dest="artifact_command", required=True)
    artifact_list = artifact_subparsers.add_parser("list", help="List artifact versions for one step or all steps", parents=[common_parser])
    artifact_list.set_defaults(command="list-artifacts")
    artifact_list.add_argument("task_id")
    artifact_list.add_argument("item_id")
    artifact_list.add_argument("step", nargs="?", choices=STEP_CHOICES)
    artifact_show = artifact_subparsers.add_parser("show", help="Show one artifact payload", parents=[common_parser])
    artifact_show.set_defaults(command="show-artifact")
    artifact_show.add_argument("task_id")
    artifact_show.add_argument("item_id")
    artifact_show.add_argument("step", choices=STEP_CHOICES)
    artifact_show.add_argument("version")
    artifact_use = artifact_subparsers.add_parser("use", help="Switch the active version for one step", parents=[common_parser])
    artifact_use.set_defaults(command="set-current-version")
    artifact_use.add_argument("task_id")
    artifact_use.add_argument("item_id")
    artifact_use.add_argument("step", choices=STEP_CHOICES)
    artifact_use.add_argument("version")

    image_group = subparsers.add_parser("image", help="Async image job commands", parents=[common_parser])
    image_subparsers = image_group.add_subparsers(dest="image_command", required=True)
    image_pending_group = image_subparsers.add_parser("pending", help="List pending async image jobs", parents=[common_parser])
    image_pending_group.set_defaults(command="image-pending")
    image_pending_group.add_argument("task_id")
    image_pending_group.add_argument("item_id")
    image_poll_group = image_subparsers.add_parser("poll", help="Poll async image generation", parents=[common_parser])
    image_poll_group.set_defaults(command="image-poll")
    image_poll_group.add_argument("task_id")
    image_poll_group.add_argument("item_id")
    image_poll_group.add_argument("--version")
    image_cancel_group = image_subparsers.add_parser("cancel", help="Cancel local waiting for pending image jobs", parents=[common_parser])
    image_cancel_group.set_defaults(command="image-cancel")
    image_cancel_group.add_argument("task_id")
    image_cancel_group.add_argument("item_id")
    image_star_group = image_subparsers.add_parser("star", help="Add one image version to the starred set", parents=[common_parser])
    image_star_group.set_defaults(command="image-star")
    image_star_group.add_argument("task_id")
    image_star_group.add_argument("item_id")
    image_star_group.add_argument("version")
    image_unstar_group = image_subparsers.add_parser("unstar", help="Remove one image version from the starred set", parents=[common_parser])
    image_unstar_group.set_defaults(command="image-unstar")
    image_unstar_group.add_argument("task_id")
    image_unstar_group.add_argument("item_id")
    image_unstar_group.add_argument("version")
    image_starred_group = image_subparsers.add_parser("starred", help="List starred image versions in one task", parents=[common_parser])
    image_starred_group.set_defaults(command="image-starred")
    image_starred_group.add_argument("task_id")

    provider_group = subparsers.add_parser("provider", help="Provider configuration commands", parents=[common_parser])
    provider_subparsers = provider_group.add_subparsers(dest="provider_command", required=True)
    provider_list_group = provider_subparsers.add_parser("list", help="List configured providers", parents=[common_parser])
    provider_list_group.set_defaults(command="provider-list")
    provider_show_group = provider_subparsers.add_parser("show", help="Show one provider config", parents=[common_parser])
    provider_show_group.set_defaults(command="provider-show")
    provider_show_group.add_argument("provider_id")
    provider_add_group = provider_subparsers.add_parser("add", help="Add one custom provider", parents=[common_parser])
    provider_add_group.set_defaults(command="provider-add")
    provider_add_group.add_argument("--label", required=True)
    provider_add_group.add_argument("--provider-type", required=True, choices=["openai_compatible", "async_image", "gemini_native"])
    provider_add_group.add_argument("--base-url", required=True)
    provider_add_group.add_argument("--api-key", default="")
    provider_add_group.add_argument("--image-max-concurrency", type=int)
    provider_update_group = provider_subparsers.add_parser("update", help="Update one provider config", parents=[common_parser])
    provider_update_group.set_defaults(command="provider-update")
    provider_update_group.add_argument("provider_id")
    provider_update_group.add_argument("--label")
    provider_update_group.add_argument("--provider-type", choices=["openai_compatible", "async_image", "gemini_native"])
    provider_update_group.add_argument("--base-url")
    provider_update_group.add_argument("--api-key")
    provider_update_group.add_argument("--image-max-concurrency", type=int)
    provider_delete_group = provider_subparsers.add_parser("delete", help="Delete one custom provider", parents=[common_parser])
    provider_delete_group.set_defaults(command="provider-delete")
    provider_delete_group.add_argument("provider_id")
    provider_sync_group = provider_subparsers.add_parser("sync-models", help="Sync models for one provider", parents=[common_parser])
    provider_sync_group.set_defaults(command="provider-sync-models")
    provider_sync_group.add_argument("provider_id")
    provider_set_default_group = provider_subparsers.add_parser(
        "set-default",
        help="Set the global default provider/model for one step",
        parents=[common_parser],
    )
    provider_set_default_group.set_defaults(command="provider-set-default")
    provider_set_default_group.add_argument("--step", required=True, choices=STEP_CHOICES)
    provider_set_default_group.add_argument("--provider", required=True)
    provider_set_default_group.add_argument("--model", required=True)

    export_group = subparsers.add_parser("export", help="Export commands", parents=[common_parser])
    export_subparsers = export_group.add_subparsers(dest="export_command", required=True)
    export_starred_group = export_subparsers.add_parser("starred", help="Export all starred images in a task", parents=[common_parser])
    export_starred_group.set_defaults(command="export-starred")
    export_starred_group.add_argument("task_id")

    runtime_group = subparsers.add_parser("runtime", help="Runtime resolution commands", parents=[common_parser])
    runtime_subparsers = runtime_group.add_subparsers(dest="runtime_command", required=True)
    runtime_resolve_group = runtime_subparsers.add_parser("resolve", help="Resolve effective runtime for one item step", parents=[common_parser])
    runtime_resolve_group.set_defaults(command="runtime-resolve")
    runtime_resolve_group.add_argument("task_id")
    runtime_resolve_group.add_argument("item_id")
    runtime_resolve_group.add_argument("--step", required=True, choices=STEP_CHOICES)

    pipeline_group = subparsers.add_parser("pipeline", help="Pipeline orchestration commands", parents=[common_parser])
    pipeline_subparsers = pipeline_group.add_subparsers(dest="pipeline_command", required=True)
    pipeline_run = pipeline_subparsers.add_parser("run", help="Run a task or one item end-to-end", parents=[common_parser])
    pipeline_run.set_defaults(command="run-pipeline")
    pipeline_run.add_argument("task_id")
    pipeline_run.add_argument("--item-id")
    pipeline_run.add_argument(
        "--no-auto-approve",
        action="store_true",
        help="Stop after each generated step instead of auto-approving it",
    )
    pipeline_run.add_argument("--stop-at", choices=STATUS_CHOICES)
    pipeline_run.add_argument("--parallel", type=int, default=1)
    pipeline_run.add_argument(
        "--image-concurrency",
        type=int,
        default=1,
        help="Batch-level image generation concurrency. Actual provider submission still respects each provider limit.",
    )
    pipeline_run.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Delay in seconds between batch item submissions",
    )

    return parser


def _create_task_from_args(args: argparse.Namespace) -> dict:
    if args.input_file:
        payload = _load_task_payload(args.input_file)
        return create_task(
            task_name=payload.get("task_name", args.task_name),
            project_background=payload.get("project_background", payload.get("project_context", args.project_background)),
            style_requirements=payload.get("style_requirements", args.style_requirements),
            asset_domain=payload.get("asset_domain", args.asset_domain),
            items=payload["items"],
            style_spec=payload.get("style_spec"),
            runtime_config=payload.get("runtime_config"),
            task_id=args.task_id,
        )

    return create_task(
        task_name=args.task_name,
        project_background=args.project_background,
        style_requirements=args.style_requirements,
        asset_domain=args.asset_domain,
        task_id=args.task_id,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "create-task":
            task = _create_task_from_args(args)
            payload = {
                "ok": True,
                "action": "task.create",
                "task_id": task["task_id"],
                "task_dir": str(task_dir(task["task_id"])),
            }
            if args.json:
                _emit(payload, as_json=True)
            else:
                print(f"Created {task['task_id']} at {task_dir(task['task_id'])}")
            return 0

        if args.command == "run-step":
            result = run_step(args.task_id, args.item_id, args.step)
            _emit(result, as_json=args.json)
            return 0

        if args.command == "create-item":
            item = create_item(
                args.task_id,
                item_id=args.item_id,
                asset_type=args.asset_type,
                title=args.title,
                description=args.description,
                category=args.category,
                extra_context=args.extra_context,
            )
            _emit(item, as_json=args.json)
            return 0

        if args.command == "update-item":
            item = update_item(
                args.task_id,
                args.item_id,
                asset_type=args.asset_type,
                title=args.title,
                description=args.description,
                category=args.category,
                extra_context=args.extra_context,
            )
            _emit(item, as_json=args.json)
            return 0

        if args.command == "approve-step":
            item_id, step = _normalize_step_target(args)
            if args.all_items:
                result = _bulk_step_action(args.task_id, step=step, action="approve")
            else:
                if not item_id:
                    raise ValueError("item_id is required unless --all-items is set")
                result = approve_step(args.task_id, item_id, step)
            _emit(result, as_json=args.json)
            return 0

        if args.command == "run-pipeline":
            result = run_pipeline(
                args.task_id,
                item_id=args.item_id,
                auto_approve=not args.no_auto_approve,
                stop_at_status=args.stop_at,
                parallel=args.parallel,
                delay_seconds=args.delay,
                image_concurrency=max(1, args.image_concurrency),
            )
            _emit(result, as_json=args.json)
            return 0

        if args.command == "list-tasks":
            _emit(list_tasks(), as_json=args.json)
            return 0

        if args.command == "show-task":
            task = load_task(args.task_id)
            task["batch_metrics"] = compute_batch_metrics(args.task_id)
            _emit(task, as_json=args.json)
            return 0

        if args.command == "update-task":
            task = update_task_settings(
                args.task_id,
                task_name=args.task_name,
                project_background=args.project_background,
                style_requirements=args.style_requirements,
                asset_domain=args.asset_domain,
            )
            if args.image_aspect_ratio is not None or args.image_resolution is not None:
                runtime_config = update_runtime_config(
                    args.task_id,
                    image_aspect_ratio=args.image_aspect_ratio,
                    image_resolution=args.image_resolution,
                )
                task["runtime_config"] = runtime_config
            _emit(task, as_json=args.json)
            return 0

        if args.command == "task-metrics":
            _emit(compute_batch_metrics(args.task_id), as_json=args.json)
            return 0

        if args.command == "list-items":
            _emit(list_items(args.task_id), as_json=args.json)
            return 0

        if args.command == "show-item":
            _emit(load_item(args.task_id, args.item_id), as_json=args.json)
            return 0

        if args.command == "list-artifacts":
            _emit(_list_artifacts_any(args.task_id, args.item_id, args.step), as_json=args.json)
            return 0

        if args.command == "show-artifact":
            _emit(load_artifact(args.task_id, args.item_id, args.step, args.version), as_json=args.json)
            return 0

        if args.command == "edit-brief":
            result = edit_brief(
                args.task_id,
                args.item_id,
                title=args.title,
                description=args.description,
                keywords=_parse_keywords(args.keywords),
                icon_subject=args.icon_subject,
                visual_focus=args.visual_focus,
                note=args.note,
            )
            _emit(result, as_json=args.json)
            return 0

        if args.command == "edit-prompt":
            result = edit_prompt(
                args.task_id,
                args.item_id,
                prompt=args.prompt,
                negative_prompt=args.negative_prompt,
                note=args.note,
            )
            _emit(result, as_json=args.json)
            return 0

        if args.command == "set-current-version":
            result = set_current_version(
                args.task_id,
                args.item_id,
                args.step,
                args.version,
            )
            _emit(result, as_json=args.json)
            return 0

        if args.command == "rollback-step":
            item_id, step = _normalize_step_target(args)
            if args.all_items:
                result = _bulk_step_action(args.task_id, step=step, action="rollback")
            else:
                if not item_id:
                    raise ValueError("item_id is required unless --all-items is set")
                result = rollback_step(
                    args.task_id,
                    item_id,
                    step,
                )
            _emit(result, as_json=args.json)
            return 0

        if args.command == "capabilities":
            payload = {
                "supports_json": True,
                "commands": sorted(COMMAND_SPECS),
                "aliases": COMMAND_ALIASES,
            }
            if args.verbose:
                payload["specs"] = [_command_schema(name) for name in sorted({*COMMAND_SPECS, *COMMAND_ALIASES})]
            _emit(payload, as_json=True)
            return 0

        if args.command == "schema":
            if args.schema_command == "command":
                _emit(_command_schema(args.name), as_json=True)
                return 0
            if args.schema_command == "state-machine":
                _emit(_state_machine_schema(), as_json=True)
                return 0
            return 0

        if args.command == "workflow-help":
            payload = _workflow_help()
            if args.name:
                payload = {
                    "workflows": [workflow for workflow in payload["workflows"] if workflow["name"] == args.name]
                }
            _emit(payload, as_json=True)
            return 0

        if args.command == "available-actions":
            _emit(_available_actions(args.task_id, args.item_id), as_json=True)
            return 0

        if args.command == "provider-list":
            _emit(_list_provider_entries(), as_json=True)
            return 0

        if args.command == "provider-show":
            _emit(_load_provider_config(args.provider_id), as_json=True)
            return 0

        if args.command == "provider-add":
            result = create_custom_provider(
                label=args.label,
                provider_type=args.provider_type,
                base_url=args.base_url,
                api_key=args.api_key,
                image_max_concurrency=max(1, args.image_max_concurrency)
                if args.image_max_concurrency is not None
                else None,
            )
            _emit(result, as_json=True)
            return 0

        if args.command == "provider-update":
            settings = load_global_settings()
            if args.provider_id not in settings.get("providers", {}) and not any(
                row.get("id") == args.provider_id for row in settings.get("custom_providers", [])
            ):
                raise ValueError(f"Unsupported provider: {args.provider_id}")
            result = update_provider_settings(
                args.provider_id,
                provider_type=args.provider_type,
                label=args.label,
                base_url=args.base_url,
                api_key=args.api_key,
                image_max_concurrency=max(1, args.image_max_concurrency)
                if args.image_max_concurrency is not None
                else UNSET,
            )
            _emit(result, as_json=True)
            return 0

        if args.command == "provider-delete":
            settings = load_global_settings()
            if not any(row.get("id") == args.provider_id for row in settings.get("custom_providers", [])):
                raise ValueError(f"Unsupported provider: {args.provider_id}")
            result = delete_custom_provider(args.provider_id)
            _emit(result, as_json=True)
            return 0

        if args.command == "provider-sync-models":
            settings = load_global_settings()
            config = provider_settings_for(settings, args.provider_id)
            if not config:
                raise ValueError(f"Unsupported provider: {args.provider_id}")
            api_key = config.get("api_key", "")
            models = sync_provider_models(args.provider_id, api_key, config)
            update_provider_settings(
                args.provider_id,
                models=models,
                last_error=None,
            )
            _emit(
                {
                    "ok": True,
                    "provider_id": args.provider_id,
                    "model_count": len(models),
                    "models": models,
                },
                as_json=True,
            )
            return 0

        if args.command == "provider-set-default":
            settings = set_global_default(
                args.step,
                provider=args.provider,
                model=args.model,
            )
            selection = settings["defaults"][args.step]
            _emit(
                {
                    "step": args.step,
                    "provider": selection["provider"],
                    "model": selection["model"],
                    "source": "global",
                },
                as_json=True,
            )
            return 0

        if args.command == "image-pending":
            _emit(_pending_image_jobs(args.task_id, args.item_id), as_json=True)
            return 0

        if args.command == "image-poll":
            if args.version:
                result = poll_image_generation_version(args.task_id, args.item_id, args.version)
            else:
                result = poll_image_generation(args.task_id, args.item_id)
            _emit(result, as_json=True)
            return 0

        if args.command == "image-cancel":
            result = cancel_pending_image_generations(args.task_id, args.item_id)
            _emit(result, as_json=True)
            return 0

        if args.command == "image-star":
            result = _set_starred_image_version(args.task_id, args.item_id, args.version, starred=True)
            _emit(result, as_json=args.json)
            return 0

        if args.command == "image-unstar":
            result = _set_starred_image_version(args.task_id, args.item_id, args.version, starred=False)
            _emit(result, as_json=args.json)
            return 0

        if args.command == "image-starred":
            _emit(_starred_image_versions(args.task_id), as_json=args.json)
            return 0

        if args.command == "export-starred":
            archive_path = export_starred_images_zip(args.task_id)
            _emit(
                {
                    "ok": True,
                    "task_id": args.task_id,
                    "archive_path": str(archive_path),
                },
                as_json=args.json,
            )
            return 0

        if args.command == "runtime-resolve":
            _emit(_runtime_resolution(args.task_id, args.item_id, args.step), as_json=args.json)
            return 0
    except KeyboardInterrupt:
        _emit(
            {
                "ok": False,
                "error_code": "INTERRUPTED",
                "message": "Interrupted by user",
            },
            as_json=getattr(args, "json", False),
        )
        return 130
    except Exception as exc:
        return _emit_error(exc, as_json=getattr(args, "json", False))

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
