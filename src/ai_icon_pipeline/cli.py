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
    create_item,
    create_task,
    list_artifacts,
    list_items,
    load_artifact,
    load_item,
    load_task,
    task_dir,
    update_item,
)
from .providers.registry import ProviderRequestError
from .providers.registry import sync_provider_models
from .state_machine import APPROVAL_RULES, GENERATION_RULES, StateMachineError
from .settings import (
    create_custom_provider,
    delete_custom_provider,
    load_global_settings,
    provider_settings_for,
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
        "args": ["task_id", "item_id", "step"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["task_id", "item_id", "step", "status", "current_versions"]},
        "errors": ["TASK_NOT_FOUND", "ITEM_NOT_FOUND", "STATE_TRANSITION_INVALID"],
    },
    "run-pipeline": {
        "group": "pipeline",
        "description": "Run a task or one item end-to-end",
        "args": ["task_id", "--item-id", "--no-auto-approve"],
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
        "args": ["task_id", "item_id", "step"],
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
        "args": ["--label", "--provider-type", "--base-url", "--api-key"],
        "supports_json": True,
        "output": {"type": "object", "keys": ["providers", "custom_providers"]},
        "errors": ["VALIDATION_ERROR"],
    },
    "provider-update": {
        "group": "provider",
        "description": "Update one provider config",
        "args": ["provider_id", "--label", "--provider-type", "--base-url", "--api-key"],
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
    spec = COMMAND_SPECS[command_name]
    return {
        "command": command_name,
        "group": spec["group"],
        "description": spec["description"],
        "args": spec["args"],
        "supports_json": spec["supports_json"],
        "output": spec.get("output", {}),
        "errors": spec.get("errors", []),
    }


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
    approve.add_argument("item_id")
    approve.add_argument("step", choices=STEP_CHOICES)

    run_all = subparsers.add_parser("run-pipeline", help="Run a task or one item end-to-end", parents=[common_parser])
    run_all.add_argument("task_id")
    run_all.add_argument("--item-id")
    run_all.add_argument(
        "--no-auto-approve",
        action="store_true",
        help="Stop after each generated step instead of auto-approving it",
    )

    show = subparsers.add_parser("show-task", help="Show current task snapshot", parents=[common_parser])
    show.add_argument("task_id")

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
    rollback_parser.add_argument("item_id")
    rollback_parser.add_argument("step", choices=[STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT])

    capabilities = subparsers.add_parser("capabilities", help="Show discoverable CLI capabilities", parents=[common_parser])
    capabilities.add_argument("--verbose", action="store_true")

    schema = subparsers.add_parser("schema", help="Show machine-readable schemas", parents=[common_parser])
    schema_subparsers = schema.add_subparsers(dest="schema_command", required=True)
    schema_command = schema_subparsers.add_parser("command", help="Show one command schema", parents=[common_parser])
    schema_command.add_argument("name", choices=sorted(COMMAND_SPECS))
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
    provider_add.add_argument("--provider-type", required=True, choices=["openai_compatible", "async_image"])
    provider_add.add_argument("--base-url", required=True)
    provider_add.add_argument("--api-key", default="")
    provider_update = subparsers.add_parser("provider-update", help="Update one provider config", parents=[common_parser])
    provider_update.add_argument("provider_id")
    provider_update.add_argument("--label")
    provider_update.add_argument("--provider-type", choices=["openai_compatible", "async_image", "gemini_native", "mock"])
    provider_update.add_argument("--base-url")
    provider_update.add_argument("--api-key")
    provider_delete = subparsers.add_parser("provider-delete", help="Delete one custom provider", parents=[common_parser])
    provider_delete.add_argument("provider_id")
    provider_sync = subparsers.add_parser("provider-sync-models", help="Sync models for one provider", parents=[common_parser])
    provider_sync.add_argument("provider_id")

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
            result = approve_step(args.task_id, args.item_id, args.step)
            _emit(result, as_json=args.json)
            return 0

        if args.command == "run-pipeline":
            result = run_pipeline(
                args.task_id,
                item_id=args.item_id,
                auto_approve=not args.no_auto_approve,
            )
            _emit(result, as_json=args.json)
            return 0

        if args.command == "show-task":
            _emit(load_task(args.task_id), as_json=args.json)
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
            result = rollback_step(
                args.task_id,
                args.item_id,
                args.step,
            )
            _emit(result, as_json=args.json)
            return 0

        if args.command == "capabilities":
            payload = {
                "supports_json": True,
                "commands": sorted(COMMAND_SPECS),
            }
            if args.verbose:
                payload["specs"] = [_command_schema(name) for name in sorted(COMMAND_SPECS)]
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
                last_error="",
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
    except Exception as exc:
        return _emit_error(exc, as_json=getattr(args, "json", False))

    parser.error(f"Unknown command: {args.command}")
    return 2
