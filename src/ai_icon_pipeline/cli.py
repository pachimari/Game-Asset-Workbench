from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import STEP_BRIEF_GENERATION, STEP_IMAGE_GENERATION, STEP_IMAGE_PROMPT
from .pipeline import (
    approve_step,
    edit_brief,
    edit_prompt,
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


STEP_CHOICES = [STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT, STEP_IMAGE_GENERATION]


def _load_task_payload(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_keywords(raw_keywords: str | None) -> list[str] | None:
    if raw_keywords is None:
        return None
    return [keyword.strip() for keyword in raw_keywords.split(",") if keyword.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-icon-pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-task", help="Create a batch task")
    create.add_argument("--task-name", default="Untitled icon batch")
    create.add_argument("--project-background", default="")
    create.add_argument("--style-requirements", default="")
    create.add_argument("--asset-domain", default="game_icon_assets")
    create.add_argument("--task-id")
    create.add_argument("--input-file", help="JSON file containing task metadata and optional items")

    create_item_parser = subparsers.add_parser("create-item", help="Create one item inside a task")
    create_item_parser.add_argument("task_id")
    create_item_parser.add_argument("--item-id")
    create_item_parser.add_argument("--asset-type", default="generic_icon")
    create_item_parser.add_argument("--title", default="")
    create_item_parser.add_argument("--description", default="")
    create_item_parser.add_argument("--category", default="")
    create_item_parser.add_argument("--extra-context", default="")

    update_item_parser = subparsers.add_parser("update-item", help="Update one item source payload")
    update_item_parser.add_argument("task_id")
    update_item_parser.add_argument("item_id")
    update_item_parser.add_argument("--asset-type")
    update_item_parser.add_argument("--title")
    update_item_parser.add_argument("--description")
    update_item_parser.add_argument("--category")
    update_item_parser.add_argument("--extra-context")

    run_single = subparsers.add_parser("run-step", help="Run a single step for one item")
    run_single.add_argument("task_id")
    run_single.add_argument("item_id")
    run_single.add_argument("step", choices=STEP_CHOICES)

    approve = subparsers.add_parser("approve-step", help="Approve one generated step")
    approve.add_argument("task_id")
    approve.add_argument("item_id")
    approve.add_argument("step", choices=STEP_CHOICES)

    run_all = subparsers.add_parser("run-pipeline", help="Run a task or one item end-to-end")
    run_all.add_argument("task_id")
    run_all.add_argument("--item-id")
    run_all.add_argument(
        "--no-auto-approve",
        action="store_true",
        help="Stop after each generated step instead of auto-approving it",
    )

    show = subparsers.add_parser("show-task", help="Show current task snapshot")
    show.add_argument("task_id")

    list_items_parser = subparsers.add_parser("list-items", help="List items in a task")
    list_items_parser.add_argument("task_id")

    show_item = subparsers.add_parser("show-item", help="Show one item snapshot")
    show_item.add_argument("task_id")
    show_item.add_argument("item_id")

    list_artifacts_parser = subparsers.add_parser(
        "list-artifacts", help="List artifact versions for one step"
    )
    list_artifacts_parser.add_argument("task_id")
    list_artifacts_parser.add_argument("item_id")
    list_artifacts_parser.add_argument("step", choices=STEP_CHOICES)

    show_artifact_parser = subparsers.add_parser(
        "show-artifact", help="Show one artifact payload"
    )
    show_artifact_parser.add_argument("task_id")
    show_artifact_parser.add_argument("item_id")
    show_artifact_parser.add_argument("step", choices=STEP_CHOICES)
    show_artifact_parser.add_argument("version")

    edit_brief_parser = subparsers.add_parser("edit-brief", help="Create a manual brief version")
    edit_brief_parser.add_argument("task_id")
    edit_brief_parser.add_argument("item_id")
    edit_brief_parser.add_argument("--title")
    edit_brief_parser.add_argument("--description")
    edit_brief_parser.add_argument("--keywords")
    edit_brief_parser.add_argument("--icon-subject")
    edit_brief_parser.add_argument("--visual-focus")
    edit_brief_parser.add_argument("--note")

    edit_prompt_parser = subparsers.add_parser("edit-prompt", help="Create a manual prompt version")
    edit_prompt_parser.add_argument("task_id")
    edit_prompt_parser.add_argument("item_id")
    edit_prompt_parser.add_argument("--prompt")
    edit_prompt_parser.add_argument("--negative-prompt")
    edit_prompt_parser.add_argument("--note")

    set_current_parser = subparsers.add_parser(
        "set-current-version", help="Switch the active version for one step"
    )
    set_current_parser.add_argument("task_id")
    set_current_parser.add_argument("item_id")
    set_current_parser.add_argument("step", choices=STEP_CHOICES)
    set_current_parser.add_argument("version")

    rollback_parser = subparsers.add_parser(
        "rollback-step", help="Move an item back to a previous stage using the latest version there"
    )
    rollback_parser.add_argument("task_id")
    rollback_parser.add_argument("item_id")
    rollback_parser.add_argument("step", choices=[STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT])

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

    if args.command == "create-task":
        task = _create_task_from_args(args)
        print(f"Created {task['task_id']} at {task_dir(task['task_id'])}")
        return 0

    if args.command == "run-step":
        result = run_step(args.task_id, args.item_id, args.step)
        print(json.dumps(result, ensure_ascii=False, indent=2))
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
        print(json.dumps(item, ensure_ascii=False, indent=2))
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
        print(json.dumps(item, ensure_ascii=False, indent=2))
        return 0

    if args.command == "approve-step":
        result = approve_step(args.task_id, args.item_id, args.step)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "run-pipeline":
        result = run_pipeline(
            args.task_id,
            item_id=args.item_id,
            auto_approve=not args.no_auto_approve,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "show-task":
        print(json.dumps(load_task(args.task_id), ensure_ascii=False, indent=2))
        return 0

    if args.command == "list-items":
        print(json.dumps(list_items(args.task_id), ensure_ascii=False, indent=2))
        return 0

    if args.command == "show-item":
        print(json.dumps(load_item(args.task_id, args.item_id), ensure_ascii=False, indent=2))
        return 0

    if args.command == "list-artifacts":
        print(
            json.dumps(
                list_artifacts(args.task_id, args.item_id, args.step),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "show-artifact":
        print(
            json.dumps(
                load_artifact(args.task_id, args.item_id, args.step, args.version),
                ensure_ascii=False,
                indent=2,
            )
        )
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
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "edit-prompt":
        result = edit_prompt(
            args.task_id,
            args.item_id,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            note=args.note,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "set-current-version":
        result = set_current_version(
            args.task_id,
            args.item_id,
            args.step,
            args.version,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "rollback-step":
        result = rollback_step(
            args.task_id,
            args.item_id,
            args.step,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
