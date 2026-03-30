from __future__ import annotations

import shutil

from .config import (
    STATUS_BRIEF_APPROVED,
    STATUS_BRIEF_GENERATED,
    STATUS_COMPLETED,
    STATUS_DRAFT,
    STATUS_FAILED,
    STATUS_IMAGE_GENERATING,
    STATUS_IMAGE_GENERATED,
    STATUS_PROMPT_APPROVED,
    STATUS_PROMPT_GENERATED,
    STEP_BRIEF_GENERATION,
    STEP_IMAGE_GENERATION,
    STEP_IMAGE_PROMPT,
)
from .provider_runtime import (
    generate_brief_output,
    generate_image_candidates,
    generate_prompt_output,
)
from .providers.registry import get_async_image_provider
from .settings import load_global_settings, provider_settings_for, resolve_stage_selection
from .state_machine import TERMINAL_STATUSES, validate_approval, validate_generation
from .storage import (
    append_event,
    append_item_event,
    load_artifact,
    load_item,
    list_artifacts,
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


GENERATED_STATUS_BY_STEP = {
    STEP_BRIEF_GENERATION: STATUS_BRIEF_GENERATED,
    STEP_IMAGE_PROMPT: STATUS_PROMPT_GENERATED,
    STEP_IMAGE_GENERATION: STATUS_IMAGE_GENERATED,
}

DOWNSTREAM_STEPS = {
    STEP_BRIEF_GENERATION: [STEP_IMAGE_PROMPT, STEP_IMAGE_GENERATION],
    STEP_IMAGE_PROMPT: [STEP_IMAGE_GENERATION],
    STEP_IMAGE_GENERATION: [],
}

PENDING_ASYNC_STATUSES = {"queued", "processing", "pending", "running", "in_progress"}


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


def _set_metrics_status(task_id: str, item_id: str, status: str) -> None:
    metrics = load_metrics(task_id, item_id)
    metrics["status"] = status
    if status != STATUS_COMPLETED:
        metrics["end_time"] = None
    save_metrics(task_id, item_id, metrics)


def _mark_step_failed(
    task_id: str,
    item_id: str,
    step: str,
    *,
    source: str,
    provider_id: str,
    model_id: str,
    error_message: str,
) -> None:
    item = load_item(task_id, item_id)
    item["status"] = STATUS_FAILED
    save_item(task_id, item)
    _set_metrics_status(task_id, item_id, STATUS_FAILED)
    event = {
        "timestamp": utc_now(),
        "source": source,
        "action": f"fail_{step}",
        "item_id": item_id,
        "step": step,
        "provider": provider_id,
        "model": model_id,
        "error": error_message,
        "to": STATUS_FAILED,
    }
    append_item_event(task_id, item_id, event)
    append_event(task_id, event)
    refresh_task_summary(task_id)


def _reset_downstream(item: dict, step: str) -> None:
    for downstream_step in DOWNSTREAM_STEPS[step]:
        item["current_versions"][downstream_step] = None


def _latest_successful_image_version(task_id: str, item_id: str) -> str | None:
    latest = None
    for artifact_meta in list_artifacts(task_id, item_id, STEP_IMAGE_GENERATION):
        artifact = load_artifact(task_id, item_id, STEP_IMAGE_GENERATION, artifact_meta["version"])
        if artifact.get("output", {}).get("candidates"):
            latest = artifact_meta["version"]
    return latest


def _effective_runtime_config(task_id: str, item: dict) -> dict:
    runtime_config = load_runtime_config(task_id)
    runtime_overrides = item.get("runtime_overrides", {})
    if runtime_overrides.get("image_aspect_ratio"):
        runtime_config["image_aspect_ratio"] = runtime_overrides["image_aspect_ratio"]
    if runtime_overrides.get("image_resolution"):
        runtime_config["image_resolution"] = runtime_overrides["image_resolution"]
    runtime_config["image_size"] = (
        f"{runtime_config.get('image_aspect_ratio', '1:1')} / {runtime_config.get('image_resolution', '1K')}"
    )
    return runtime_config


def _artifact_job_status(payload: dict) -> str | None:
    return payload.get("async_job", {}).get("status")


def _select_current_version(
    task_id: str,
    item_id: str,
    step: str,
    version: str,
    *,
    source: str,
    action: str,
) -> dict:
    item = load_item(task_id, item_id)
    load_artifact(task_id, item_id, step, version)
    item["current_versions"][step] = version
    _reset_downstream(item, step)
    item["status"] = GENERATED_STATUS_BY_STEP[step]
    save_item(task_id, item)
    _set_metrics_status(task_id, item_id, item["status"])
    event = {
        "timestamp": utc_now(),
        "source": source,
        "action": action,
        "step": step,
        "version": version,
        "to": item["status"],
    }
    append_item_event(task_id, item_id, event)
    append_event(task_id, {"item_id": item_id, **event})
    refresh_task_summary(task_id)
    return {
        "task_id": task_id,
        "item_id": item_id,
        "step": step,
        "version": version,
        "status": item["status"],
    }


def run_step(task_id: str, item_id: str, step: str, *, source: str = "cli") -> dict:
    task = load_task(task_id)
    item = load_item(task_id, item_id)
    global_settings = load_global_settings()
    selected_runtime = resolve_stage_selection(task, item, global_settings, step)
    provider_id = selected_runtime["provider"]
    model_id = selected_runtime["model"]
    provider_settings = provider_settings_for(global_settings, provider_id)
    api_key = provider_settings.get("api_key", "")
    prompt_templates = global_settings.get("prompt_templates", {})
    next_status = validate_generation(step, item["status"])

    try:
        if step == STEP_BRIEF_GENERATION:
            output = generate_brief_output(
                provider_id=provider_id,
                provider_config=provider_settings,
                api_key=api_key,
                model=model_id,
                asset_type=item["asset_type"],
                title=item.get("title", ""),
                description=item["description"],
                category=item.get("category", ""),
                project_background=task.get("project_background", task.get("project_context", "")),
                style_requirements=task.get("style_requirements", ""),
                extra_context=item.get("extra_context", ""),
                system_prompt=prompt_templates.get("brief_system_prompt"),
            )
            payload = {
                "step": step,
                "provider": provider_id,
                "model": model_id,
                "created_at": utc_now(),
                "input": {
                    "asset_type": item["asset_type"],
                    "title": item.get("title", ""),
                    "description": item["description"],
                    "category": item.get("category", ""),
                    "project_background": task.get("project_background", task.get("project_context", "")),
                    "style_requirements": task.get("style_requirements", ""),
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
            runtime_config = _effective_runtime_config(task_id, item)
            style_spec = load_style_spec(task_id)
            output = generate_prompt_output(
                provider_id=provider_id,
                provider_config=provider_settings,
                api_key=api_key,
                model=model_id,
                brief_output=brief_artifact["output"],
                style_spec=style_spec,
                runtime_config=runtime_config,
                system_prompt=prompt_templates.get("prompt_system_prompt"),
            )
            payload = {
                "step": step,
                "provider": provider_id,
                "model": model_id,
                "created_at": utc_now(),
                "input": {
                    "brief_version": brief_version,
                    "style_spec": style_spec,
                    "selected_runtime": selected_runtime,
                },
                "output": output,
            }
            version = None
        elif step == STEP_IMAGE_GENERATION:
            prompt_version = item["current_versions"]["image_prompt"]
            if not prompt_version:
                raise ValueError("No approved prompt version found for image generation")
            runtime_config = _effective_runtime_config(task_id, item)
            version = next_version(task_id, item_id, step)
            prompt_artifact = load_artifact(task_id, item_id, STEP_IMAGE_PROMPT, prompt_version)
            if provider_settings.get("provider_type") == "async_image":
                async_provider = get_async_image_provider(provider_id, provider_settings)
                composed_prompt = prompt_artifact["output"].get("prompt", "")
                negative_prompt = prompt_artifact["output"].get("negative_prompt", "")
                if negative_prompt:
                    composed_prompt += f"\nAvoid: {negative_prompt}"
                response = async_provider.submit_generation(
                    api_key=api_key,
                    model=model_id,
                    prompt=composed_prompt,
                    aspect_ratio=runtime_config.get("image_aspect_ratio", "1:1"),
                    resolution=runtime_config.get("image_resolution", "1K"),
                )
                payload = {
                    "step": step,
                    "provider": provider_id,
                    "model": model_id,
                    "created_at": utc_now(),
                    "input": {
                        "image_prompt_version": prompt_version,
                        "candidate_count": runtime_config["candidate_count"],
                        "image_size": runtime_config["image_size"],
                        "image_aspect_ratio": runtime_config.get("image_aspect_ratio", "1:1"),
                        "image_resolution": runtime_config.get("image_resolution", "1K"),
                        "selected_runtime": selected_runtime,
                    },
                    "async_job": {
                        "provider_type": provider_settings.get("provider_type"),
                        "status": response.get("status", "queued"),
                        "task_id": response.get("id"),
                        "progress": response.get("progress", 0),
                        "submitted_at": utc_now(),
                    },
                    "output": {"candidates": []},
                }
            else:
                candidates = generate_image_candidates(
                    provider_id=provider_id,
                    api_key=api_key,
                    model=model_id,
                    output_dir=item_dir(task_id, item_id) / "images",
                    version=version,
                    candidate_count=runtime_config["candidate_count"],
                    prompt=prompt_artifact["output"].get("prompt", ""),
                    negative_prompt=prompt_artifact["output"].get("negative_prompt", ""),
                    image_size=runtime_config["image_size"],
                    image_aspect_ratio=runtime_config.get("image_aspect_ratio", "1:1"),
                    image_resolution=runtime_config.get("image_resolution", "1K"),
                )
                payload = {
                    "step": step,
                    "provider": provider_id,
                    "model": model_id,
                    "created_at": utc_now(),
                    "input": {
                        "image_prompt_version": prompt_version,
                        "candidate_count": runtime_config["candidate_count"],
                        "image_size": runtime_config["image_size"],
                        "image_aspect_ratio": runtime_config.get("image_aspect_ratio", "1:1"),
                        "image_resolution": runtime_config.get("image_resolution", "1K"),
                        "selected_runtime": selected_runtime,
                    },
                    "output": {"candidates": candidates},
                }
        else:
            raise ValueError(f"Unsupported step: {step}")
    except Exception as exc:
        _mark_step_failed(
            task_id,
            item_id,
            step,
            source=source,
            provider_id=provider_id,
            model_id=model_id,
            error_message=str(exc),
        )
        raise

    version = write_artifact(task_id, item_id, step, payload, version=version)
    item["current_versions"][step] = version
    item["status"] = (
        STATUS_IMAGE_GENERATING
        if step == STEP_IMAGE_GENERATION and payload.get("async_job")
        else next_status
    )
    save_item(task_id, item)
    _touch_metrics(task_id, item_id, step)
    append_item_event(
        task_id,
        item_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": f"run_{step}",
            "to": item["status"],
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
            "to": item["status"],
            "version": version,
        },
    )
    refresh_task_summary(task_id)
    return {
        "task_id": task_id,
        "item_id": item_id,
        "step": step,
        "version": version,
        "status": item["status"],
    }


def poll_image_generation(task_id: str, item_id: str, *, source: str = "cli") -> dict:
    item = load_item(task_id, item_id)
    version = item["current_versions"].get(STEP_IMAGE_GENERATION)
    if not version:
        raise ValueError("当前没有候选图任务")
    return poll_image_generation_version(task_id, item_id, version, source=source)


def poll_image_generation_version(task_id: str, item_id: str, version: str, *, source: str = "cli") -> dict:
    item = load_item(task_id, item_id)
    artifact = load_artifact(task_id, item_id, STEP_IMAGE_GENERATION, version)
    async_job = artifact.get("async_job", {})
    task_id_remote = async_job.get("task_id")
    if not task_id_remote:
        raise ValueError("当前候选图版本不是异步任务")

    global_settings = load_global_settings()
    provider_id = artifact.get("provider", "mock")
    provider_settings = provider_settings_for(global_settings, provider_id)
    api_key = provider_settings.get("api_key", "")
    model_id = artifact.get("model", "")
    async_provider = get_async_image_provider(provider_id, provider_settings)
    response = async_provider.poll_generation(api_key=api_key, task_id=task_id_remote)
    remote_status = str(response.get("status", "")).lower()
    async_job["status"] = remote_status or async_job.get("status", "queued")
    async_job["progress"] = response.get("progress", async_job.get("progress", 0))
    async_job["updated_at"] = utc_now()

    if remote_status in PENDING_ASYNC_STATUSES:
        artifact["async_job"] = async_job
        write_artifact(task_id, item_id, STEP_IMAGE_GENERATION, artifact, version=version)
        if item["current_versions"].get(STEP_IMAGE_GENERATION) == version:
            item["status"] = STATUS_IMAGE_GENERATING
            save_item(task_id, item)
            _set_metrics_status(task_id, item_id, STATUS_IMAGE_GENERATING)
        append_item_event(
            task_id,
            item_id,
            {
                "timestamp": utc_now(),
                "source": source,
                "action": "poll_image_generation",
                "version": version,
                "remote_status": remote_status,
                "to": STATUS_IMAGE_GENERATING,
            },
        )
        append_event(
            task_id,
            {
                "timestamp": utc_now(),
                "source": source,
                "action": "poll_image_generation",
                "item_id": item_id,
                "version": version,
                "remote_status": remote_status,
                "to": STATUS_IMAGE_GENERATING,
            },
        )
        refresh_task_summary(task_id)
        return {"task_id": task_id, "item_id": item_id, "step": STEP_IMAGE_GENERATION, "version": version, "status": STATUS_IMAGE_GENERATING}

    if remote_status == "completed":
        result = response.get("result", {})
        urls = []
        if isinstance(result, dict):
            for row in result.get("data", []):
                if isinstance(row, dict) and row.get("url"):
                    urls.append(row["url"])
        if not urls:
            raise ValueError("异步图片任务已完成，但没有返回结果图 URL")
        candidates = []
        image_root = item_dir(task_id, item_id) / "images"
        for index, url in enumerate(urls, start=1):
            filename = f"{version}_candidate_{index:02d}.jpg"
            destination = image_root / filename
            async_provider.download_result(url=url, destination=destination)
            candidates.append({"candidate_id": f"candidate_{index:02d}", "image_path": filename, "source_url": url})
        artifact["async_job"] = async_job
        artifact["output"] = {"candidates": candidates}
        write_artifact(task_id, item_id, STEP_IMAGE_GENERATION, artifact, version=version)
        if item["current_versions"].get(STEP_IMAGE_GENERATION) == version:
            item["status"] = STATUS_IMAGE_GENERATED
            save_item(task_id, item)
            _set_metrics_status(task_id, item_id, STATUS_IMAGE_GENERATED)
        append_item_event(
            task_id,
            item_id,
            {
                "timestamp": utc_now(),
                "source": source,
                "action": "complete_image_generation",
                "version": version,
                "remote_status": remote_status,
                "to": STATUS_IMAGE_GENERATED,
            },
        )
        append_event(
            task_id,
            {
                "timestamp": utc_now(),
                "source": source,
                "action": "complete_image_generation",
                "item_id": item_id,
                "version": version,
                "remote_status": remote_status,
                "to": STATUS_IMAGE_GENERATED,
            },
        )
        refresh_task_summary(task_id)
        return {"task_id": task_id, "item_id": item_id, "step": STEP_IMAGE_GENERATION, "version": version, "status": STATUS_IMAGE_GENERATED}

    if remote_status in {"failed", "cancelled", "canceled"}:
        async_job["status"] = remote_status
        async_job["error"] = str(response.get("error", response))
        artifact["async_job"] = async_job
        write_artifact(task_id, item_id, STEP_IMAGE_GENERATION, artifact, version=version)
        if item["current_versions"].get(STEP_IMAGE_GENERATION) == version:
            _mark_step_failed(
                task_id,
                item_id,
                STEP_IMAGE_GENERATION,
                source=source,
                provider_id=provider_id,
                model_id=model_id,
                error_message=str(response.get("error", response)),
            )
            return {
                "task_id": task_id,
                "item_id": item_id,
                "step": STEP_IMAGE_GENERATION,
                "version": version,
                "status": STATUS_FAILED,
                "error": str(response.get("error", remote_status)),
            }
        return {
            "task_id": task_id,
            "item_id": item_id,
            "step": STEP_IMAGE_GENERATION,
            "version": version,
            "status": item.get("status"),
            "error": str(response.get("error", remote_status)),
        }

    artifact["async_job"] = async_job
    write_artifact(task_id, item_id, STEP_IMAGE_GENERATION, artifact, version=version)
    return {"task_id": task_id, "item_id": item_id, "step": STEP_IMAGE_GENERATION, "version": version, "status": item["status"]}


def cancel_pending_image_generations(task_id: str, item_id: str, *, source: str = "cli") -> dict:
    item = load_item(task_id, item_id)
    cancelled_versions: list[str] = []
    for artifact_meta in list_artifacts(task_id, item_id, STEP_IMAGE_GENERATION):
        version = artifact_meta["version"]
        artifact = load_artifact(task_id, item_id, STEP_IMAGE_GENERATION, version)
        async_job = artifact.get("async_job", {})
        status = str(async_job.get("status", "")).lower()
        if status not in PENDING_ASYNC_STATUSES:
            continue
        async_job["status"] = "cancelled_local"
        async_job["updated_at"] = utc_now()
        artifact["async_job"] = async_job
        write_artifact(task_id, item_id, STEP_IMAGE_GENERATION, artifact, version=version)
        cancelled_versions.append(version)

    if not cancelled_versions:
        raise ValueError("当前没有可中断的候选图任务")

    fallback_version = _latest_successful_image_version(task_id, item_id)
    if fallback_version:
        item["current_versions"][STEP_IMAGE_GENERATION] = fallback_version
        item["status"] = STATUS_IMAGE_GENERATED
        next_status = STATUS_IMAGE_GENERATED
    else:
        item["current_versions"][STEP_IMAGE_GENERATION] = None
        item["status"] = STATUS_PROMPT_APPROVED
        next_status = STATUS_PROMPT_APPROVED
    save_item(task_id, item)
    _set_metrics_status(task_id, item_id, next_status)
    append_item_event(
        task_id,
        item_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": "cancel_pending_image_generations",
            "cancelled_versions": cancelled_versions,
            "to": next_status,
        },
    )
    append_event(
        task_id,
        {
            "timestamp": utc_now(),
            "source": source,
            "action": "cancel_pending_image_generations",
            "item_id": item_id,
            "cancelled_versions": cancelled_versions,
            "to": next_status,
        },
    )
    refresh_task_summary(task_id)
    return {
        "task_id": task_id,
        "item_id": item_id,
        "cancelled_versions": cancelled_versions,
        "status": next_status,
        "current_version": item["current_versions"].get(STEP_IMAGE_GENERATION),
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
        approved_suffix = src.suffix or ".png"
        dst = item_dir(task_id, item_id) / "images" / f"approved{approved_suffix}"
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


def edit_brief(
    task_id: str,
    item_id: str,
    *,
    title: str | None = None,
    description: str | None = None,
    keywords: list[str] | None = None,
    icon_subject: str | None = None,
    visual_focus: str | None = None,
    note: str | None = None,
    source: str = "cli",
) -> dict:
    item = load_item(task_id, item_id)
    current_version = item["current_versions"][STEP_BRIEF_GENERATION]
    base_output = {}
    base_input = {}
    if current_version:
        artifact = load_artifact(task_id, item_id, STEP_BRIEF_GENERATION, current_version)
        base_output = artifact.get("output", {})
        base_input = artifact.get("input", {})

    payload = {
        "step": STEP_BRIEF_GENERATION,
        "provider": "manual",
        "created_at": utc_now(),
        "input": base_input,
        "note": note or "manual brief edit",
        "output": {
            "title": title if title is not None else base_output.get("title", item.get("title", "")),
            "name_source": base_output.get("name_source", "manual"),
            "description": (
                description if description is not None else base_output.get("description", item["description"])
            ),
            "keywords": keywords if keywords is not None else base_output.get("keywords", []),
            "icon_subject": (
                icon_subject
                if icon_subject is not None
                else base_output.get("icon_subject", item.get("title", "") or "图标主体")
            ),
            "visual_focus": visual_focus if visual_focus is not None else base_output.get("visual_focus", ""),
            "project_background": base_output.get("project_background", base_input.get("project_background", "")),
            "style_requirements": base_output.get("style_requirements", base_input.get("style_requirements", "")),
        },
    }
    version = write_artifact(task_id, item_id, STEP_BRIEF_GENERATION, payload, manual=True)
    return _select_current_version(
        task_id,
        item_id,
        STEP_BRIEF_GENERATION,
        version,
        source=source,
        action="edit_brief",
    )


def edit_prompt(
    task_id: str,
    item_id: str,
    *,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    note: str | None = None,
    source: str = "cli",
) -> dict:
    item = load_item(task_id, item_id)
    current_version = item["current_versions"][STEP_IMAGE_PROMPT]
    base_output = {}
    base_input = {}
    if current_version:
        artifact = load_artifact(task_id, item_id, STEP_IMAGE_PROMPT, current_version)
        base_output = artifact.get("output", {})
        base_input = artifact.get("input", {})

    payload = {
        "step": STEP_IMAGE_PROMPT,
        "provider": "manual",
        "created_at": utc_now(),
        "input": base_input,
        "note": note or "manual prompt edit",
        "output": {
            "prompt": prompt if prompt is not None else base_output.get("prompt", ""),
            "negative_prompt": (
                negative_prompt
                if negative_prompt is not None
                else base_output.get("negative_prompt", "")
            ),
            "constraints": base_output.get("constraints", {}),
        },
    }
    version = write_artifact(task_id, item_id, STEP_IMAGE_PROMPT, payload, manual=True)
    return _select_current_version(
        task_id,
        item_id,
        STEP_IMAGE_PROMPT,
        version,
        source=source,
        action="edit_prompt",
    )


def set_current_version(
    task_id: str,
    item_id: str,
    step: str,
    version: str,
    *,
    source: str = "cli",
) -> dict:
    return _select_current_version(
        task_id,
        item_id,
        step,
        version,
        source=source,
        action="set_current_version",
    )


def rollback_step(
    task_id: str,
    item_id: str,
    step: str,
    *,
    source: str = "cli",
) -> dict:
    artifacts = list_artifacts(task_id, item_id, step)
    if not artifacts:
        raise ValueError(f"No artifacts available for rollback: {task_id} {item_id} {step}")
    latest_version = artifacts[-1]["version"]
    return _select_current_version(
        task_id,
        item_id,
        step,
        latest_version,
        source=source,
        action="rollback_step",
    )


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
        if status == STATUS_IMAGE_GENERATING:
            return {"task_id": task_id, "item_id": item_id, "status": status}
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
