from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import STEP_BRIEF_GENERATION, STEP_IMAGE_GENERATION, STEP_IMAGE_PROMPT
from .pipeline import approve_step, run_pipeline, run_step
from .storage import create_task, load_item, load_task, task_dir


STEP_CHOICES = [STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT, STEP_IMAGE_GENERATION]


def _load_task_payload(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-icon-pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-task", help="Create a batch task")
    create.add_argument("--task-name", default="Untitled icon batch")
    create.add_argument("--project-context", default="通用项目")
    create.add_argument("--asset-domain", default="game_icon_assets")
    create.add_argument("--task-id")
    create.add_argument("--input-file", help="JSON file containing task metadata and items")
    create.add_argument("--asset-type")
    create.add_argument("--title", default="")
    create.add_argument("--description")
    create.add_argument("--category", default="")
    create.add_argument("--extra-context", default="")

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

    show_item = subparsers.add_parser("show-item", help="Show one item snapshot")
    show_item.add_argument("task_id")
    show_item.add_argument("item_id")

    return parser


def _create_task_from_args(args: argparse.Namespace) -> dict:
    if args.input_file:
        payload = _load_task_payload(args.input_file)
        return create_task(
            task_name=payload.get("task_name", args.task_name),
            project_context=payload.get("project_context", args.project_context),
            asset_domain=payload.get("asset_domain", args.asset_domain),
            items=payload["items"],
            style_spec=payload.get("style_spec"),
            runtime_config=payload.get("runtime_config"),
            task_id=args.task_id,
        )

    if not args.description:
        raise ValueError("Either --input-file or --description is required")

    single_item = {
        "asset_type": args.asset_type or "generic_icon",
        "title": args.title,
        "description": args.description,
        "category": args.category,
        "extra_context": args.extra_context,
    }
    return create_task(
        task_name=args.task_name,
        project_context=args.project_context,
        asset_domain=args.asset_domain,
        items=[single_item],
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

    if args.command == "show-item":
        print(json.dumps(load_item(args.task_id, args.item_id), ensure_ascii=False, indent=2))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
