from __future__ import annotations

import shutil

from .config import (
    STATUS_BRIEF_APPROVED,
    STATUS_BRIEF_GENERATED,
    STATUS_COMPLETED,
    STATUS_DRAFT,
    STATUS_IMAGE_GENERATED,
    STATUS_PROMPT_APPROVED,
    STATUS_PROMPT_GENERATED,
    STEP_BRIEF_GENERATION,
    STEP_IMAGE_GENERATION,
    STEP_IMAGE_PROMPT,
)
from .mock_providers import generate_brief, generate_image_prompt, generate_images
from .state_machine import TERMINAL_STATUSES, validate_approval, validate_generation
from .storage import (
    append_event,
    append_item_event,
    load_artifact,
    load_item,
    load_metrics,
    load_runtime_config,
    load_style_spec,
    load_task,
    next_version,
    refresh_task_summary,
    save_item,
    save_metrics,
    write_artifact,
    item_dir,
)
from .utils import utc_now


def _touch_metrics(task_id: str, item_id: str, step: str) -> None:
    metrics = load_metrics(task_id, item_id)
    metrics["iterations"][step] += 1
    metrics["api_calls"] += 1
    metrics["status"] = load_item(task_id, item_id)["status"]
    save_metrics(task_id, item_id, metrics)


def _mark_completed(task_id: str, item_id: str) -> None:
    metrics = load_metrics(task_id, item_id)
    metrics["status"] = STATUS_COMPLETED
    metrics["end_time"] = utc_now()
    save_metrics(task_id, item_id, metrics)


def run_step(task_id: str, item_id: str, step: str, *, source: str = "cli") -> dict:
    task = load_task(task_id)
    item = load_item(task_id, item_id)
    next_status = validate_generation(step, item["status"])

    if step == STEP_BRIEF_GENERATION:
        output = generate_brief(
            asset_type=item["asset_type"],
            title=item.get("title", ""),
            description=item["description"],
            category=item.get("category", ""),
            project_context=task["project_context"],
            extra_context=item.get("extra_context", ""),
        )
        payload = {
            "step": step,
            "provider": "mock",
            "created_at": utc_now(),
            "input": {
                "asset_type": item["asset_type"],
                "title": item.get("title", ""),
                "description": item["description"],
                "category": item.get("category", ""),
                "project_context": task["project_context"],
                "extra_context": item.get("extra_context", ""),
            },
            "output": output,
        }
        version = None
    elif step == STEP_IMAGE_PROMPT:
        brief_version = item["current_versions"]["brief_generation"]
        if not brief_version:
            raise ValueError("No approved brief version found for prompt generation")
        brief_artifact = load_artifact(task_id, item_id, STEP_BRIEF_GENERATION, brief_version)
        runtime_config = load_runtime_config(task_id)
        style_spec = load_style_spec(task_id)
        output = generate_image_prompt(
            brief_output=brief_artifact["output"],
            style_spec=style_spec,
            runtime_config=runtime_config,
        )
        payload = {
            "step": step,
            "provider": "mock",
            "created_at": utc_now(),
            "input": {
                "brief_version": brief_version,
                "style_spec": style_spec,
            },
            "output": output,
        }
        version = None
    elif step == STEP_IMAGE_GENERATION:
        prompt_version = item["current_versions"]["image_prompt"]
        if not prompt_version:
            raise ValueError("No approved prompt version found for image generation")
        runtime_config = load_runtime_config(task_id)
        version = next_version(task_id, item_id, step)
        candidates = generate_images(
            output_dir=item_dir(task_id, item_id) / "images",
            version=version,
            candidate_count=runtime_config["candidate_count"],
        )
        payload = {
            "step": step,
            "provider": "mock",
            "created_at": utc_now(),
            "input": {
                "image_prompt_version": prompt_version,
                "candidate_count": runtime_config["candidate_count"],
            },
            "output": {"candidates": candidates},
        }
    else:
        raise ValueError(f"Unsupported step: {step}")

    version = write_artifact(task_id, item_id, step, payload, version=version)
    item["current_versions"][step] = version
    item["status"] = next_status
    save_item(task_id, item)
    _touch_metrics(task_id, item_id, step)
    append_item_event(
        task_id,
        item_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": f"run_{step}",
            "to": next_status,
            "version": version,
        },
    )
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": f"run_{step}",
            "item_id": item_id,
            "to": next_status,
            "version": version,
        },
    )
    refresh_task_summary(task_id)
    return {
        "task_id": task_id,
        "item_id": item_id,
        "step": step,
        "version": version,
        "status": next_status,
    }


def approve_step(task_id: str, item_id: str, step: str, *, source: str = "cli") -> dict:
    item = load_item(task_id, item_id)
    next_status = validate_approval(step, item["status"])

    current_version = item["current_versions"][step]
    if not current_version:
        raise ValueError(f"No current version available for step '{step}'")

    item["status"] = next_status
    save_item(task_id, item)

    if step == STEP_IMAGE_GENERATION:
        image_artifact = load_artifact(task_id, item_id, STEP_IMAGE_GENERATION, current_version)
        first_image = image_artifact["output"]["candidates"][0]["image_path"]
        src = item_dir(task_id, item_id) / "images" / first_image
        dst = item_dir(task_id, item_id) / "images" / "approved.png"
        shutil.copyfile(src, dst)
        _mark_completed(task_id, item_id)
    else:
        metrics = load_metrics(task_id, item_id)
        metrics["status"] = next_status
        save_metrics(task_id, item_id, metrics)

    append_item_event(
        task_id,
        item_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": f"approve_{step}",
            "to": next_status,
            "version": current_version,
        },
    )
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": f"approve_{step}",
            "item_id": item_id,
            "to": next_status,
            "version": current_version,
        },
    )
    refresh_task_summary(task_id)
    return {"task_id": task_id, "item_id": item_id, "step": step, "status": next_status}


def run_item_pipeline(
    task_id: str,
    item_id: str,
    *,
    auto_approve: bool = True,
    source: str = "cli",
) -> dict:
    while True:
        item = load_item(task_id, item_id)
        status = item["status"]

        if status in TERMINAL_STATUSES:
            return {"task_id": task_id, "item_id": item_id, "status": status}

        if status == STATUS_DRAFT:
            run_step(task_id, item_id, STEP_BRIEF_GENERATION, source=source)
            continue
        if status == STATUS_BRIEF_GENERATED:
            if not auto_approve:
                return {"task_id": task_id, "item_id": item_id, "status": status}
            approve_step(task_id, item_id, STEP_BRIEF_GENERATION, source=source)
            continue
        if status == STATUS_BRIEF_APPROVED:
            run_step(task_id, item_id, STEP_IMAGE_PROMPT, source=source)
            continue
        if status == STATUS_PROMPT_GENERATED:
            if not auto_approve:
                return {"task_id": task_id, "item_id": item_id, "status": status}
            approve_step(task_id, item_id, STEP_IMAGE_PROMPT, source=source)
            continue
        if status == STATUS_PROMPT_APPROVED:
            run_step(task_id, item_id, STEP_IMAGE_GENERATION, source=source)
            continue
        if status == STATUS_IMAGE_GENERATED:
            if not auto_approve:
                return {"task_id": task_id, "item_id": item_id, "status": status}
            approve_step(task_id, item_id, STEP_IMAGE_GENERATION, source=source)
            continue

        raise ValueError(f"Unsupported item status: {status}")


def run_pipeline(
    task_id: str,
    *,
    item_id: str | None = None,
    auto_approve: bool = True,
    source: str = "cli",
) -> dict:
    task = load_task(task_id)
    item_ids = [item_id] if item_id else task["items"]
    results = []
    for current_item_id in item_ids:
        results.append(
            run_item_pipeline(
                task_id,
                current_item_id,
                auto_approve=auto_approve,
                source=source,
            )
        )
    summary = refresh_task_summary(task_id)
    return {
        "task_id": task_id,
        "task_status": summary["status"],
        "results": results,
    }
