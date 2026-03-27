from __future__ import annotations

import json
import re

from .config import STEP_BRIEF_GENERATION, STEP_IMAGE_GENERATION, STEP_IMAGE_PROMPT
from .pipeline import approve_step, poll_image_generation, rollback_step, run_step, set_current_version
from .providers.registry import get_provider
from .settings import (
    load_global_settings,
    provider_label_for,
    provider_models_for_stage,
    provider_settings_for,
    resolve_stage_selection,
)
from .storage import (
    list_artifacts,
    load_item,
    load_task,
    update_item,
    update_item_model_override,
)


ALLOWED_COMMANDS = {
    "approve_current_step": {"args": []},
    "run_step": {"args": ["step"]},
    "poll_image_generation": {"args": []},
    "rollback_step": {"args": ["step"]},
    "set_current_version": {"args": ["step", "version"]},
    "update_item_fields": {"args": ["title", "description", "category", "extra_context"]},
    "update_item_runtime": {"args": ["image_aspect_ratio", "image_resolution"]},
    "set_stage_model": {"args": ["step", "model", "provider"]},
}

ALLOWED_STEPS = {
    STEP_BRIEF_GENERATION,
    STEP_IMAGE_PROMPT,
    STEP_IMAGE_GENERATION,
}

ALLOWED_PLAN_COMMANDS = set(ALLOWED_COMMANDS)


CHAT_SYSTEM_PROMPT = """你是游戏图标工作台里的受限命令规划器。
你的任务不是自由回答，而是把用户指令翻译成一个多步执行计划。

你只能使用以下 command：
- approve_current_step
- run_step
- poll_image_generation
- rollback_step
- set_current_version
- update_item_fields
- update_item_runtime
- set_stage_model

规则：
1. 最多输出 4 步。
2. 只能操作当前条目。
3. 如果需要修改模型，优先使用用户提到的友好模型名。
4. 如果当前状态还不能直接执行某一步，请先规划必要的前置步骤。
5. 如果请求超出允许范围，请返回 steps 为 []，并说明 reason。

返回 JSON 对象，字段必须包含：
- summary: string
- reason: string
- confidence: number
- steps: array

steps 中每一项格式必须为：
- command: string
- args: object

不要输出 markdown，不要输出解释文本，只返回 JSON。"""


def _latest_version(task_id: str, item_id: str, step: str) -> str | None:
    artifacts = list_artifacts(task_id, item_id, step)
    if not artifacts:
        return None
    return artifacts[-1]["version"]


def _heuristic_plan(message: str) -> dict | None:
    text = message.strip().lower()
    if not text:
        return None

    if any(token in text for token in ["返回设计说明", "回到设计说明", "回退设计说明", "rollback brief"]):
        return {
            "summary": "回退到设计说明阶段",
            "reason": "命中设计说明回退关键词",
            "confidence": 0.98,
            "steps": [{"command": "rollback_step", "args": {"step": STEP_BRIEF_GENERATION}}],
        }
    if any(token in text for token in ["返回出图指令", "回退出图指令", "回到出图指令", "rollback prompt"]):
        return {
            "summary": "回退到出图指令阶段",
            "reason": "命中出图指令回退关键词",
            "confidence": 0.98,
            "steps": [{"command": "rollback_step", "args": {"step": STEP_IMAGE_PROMPT}}],
        }
    if re.search(r"(重跑|重新生成).*(设计说明|需求整理|brief)", text):
        return {
            "summary": "重新生成设计说明",
            "reason": "命中设计说明重跑关键词",
            "confidence": 0.98,
            "steps": [{"command": "run_step", "args": {"step": STEP_BRIEF_GENERATION}}],
        }
    if re.search(r"(重跑|重新生成).*(出图指令|prompt)", text):
        return {
            "summary": "重新生成出图指令",
            "reason": "命中出图指令重跑关键词",
            "confidence": 0.98,
            "steps": [{"command": "run_step", "args": {"step": STEP_IMAGE_PROMPT}}],
        }
    if re.search(r"(检查|查看|刷新).*(候选图|图片).*(状态|进度)", text):
        return {
            "summary": "检查候选图生成状态",
            "reason": "命中图片状态检查关键词",
            "confidence": 0.95,
            "steps": [{"command": "poll_image_generation", "args": {}}],
        }
    if re.search(r"(重跑|重新生成).*(候选图|出图|图片)", text):
        return {
            "summary": "重新生成一张候选图",
            "reason": "命中候选图重跑关键词",
            "confidence": 0.95,
            "steps": [{"command": "run_step", "args": {"step": STEP_IMAGE_GENERATION}}],
        }
    if any(token in text for token in ["通过", "确认", "采纳", "继续"]):
        return {
            "summary": "执行当前阶段的推进动作",
            "reason": "命中继续/通过关键词",
            "confidence": 0.82,
            "steps": [{"command": "approve_current_step", "args": {}}],
        }
    return None


def _available_model_context(settings: dict) -> dict[str, list[dict]]:
    return {
        step: [
            {
                "provider": row["provider"],
                "provider_label": provider_label_for(settings, row["provider"]),
                "model": row["model"],
                "label": row.get("label", row["model"]),
            }
            for row in provider_models_for_stage(settings, step)
        ]
        for step in [STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT, STEP_IMAGE_GENERATION]
    }


def _normalize_step(step: str | None) -> str | None:
    mapping = {
        "brief": STEP_BRIEF_GENERATION,
        "brief_generation": STEP_BRIEF_GENERATION,
        "设计说明": STEP_BRIEF_GENERATION,
        "prompt": STEP_IMAGE_PROMPT,
        "image_prompt": STEP_IMAGE_PROMPT,
        "出图指令": STEP_IMAGE_PROMPT,
        "image": STEP_IMAGE_GENERATION,
        "image_generation": STEP_IMAGE_GENERATION,
        "候选图": STEP_IMAGE_GENERATION,
    }
    if not step:
        return None
    return mapping.get(step, step)


def _validate_plan(raw: dict) -> dict:
    steps = raw.get("steps")
    if not isinstance(steps, list):
        steps = []
    normalized_steps = []
    for row in steps[:4]:
        if not isinstance(row, dict):
            continue
        command = row.get("command")
        args = row.get("args", {})
        if command not in ALLOWED_PLAN_COMMANDS or not isinstance(args, dict):
            continue
        normalized_steps.append({"command": command, "args": args})
    return {
        "summary": str(raw.get("summary") or "未生成有效计划"),
        "reason": str(raw.get("reason") or "模型未返回原因"),
        "confidence": float(raw.get("confidence") or 0.0),
        "steps": normalized_steps,
    }


def parse_chat_plan(task: dict, item: dict, settings: dict, message: str) -> dict:
    heuristic = _heuristic_plan(message)
    if heuristic:
        return {**heuristic, "parser": "heuristic"}

    selected_runtime = resolve_stage_selection(task, item, settings, STEP_IMAGE_PROMPT)
    provider_id = selected_runtime["provider"]
    model_id = selected_runtime["model"]
    if provider_id == "mock":
        return {
            "summary": "当前未配置真实文本模型",
            "reason": "当前未配置真实文本模型，且本地规则没有识别出指令",
            "confidence": 0.0,
            "steps": [],
            "parser": "heuristic",
        }

    provider_settings = provider_settings_for(settings, provider_id)
    api_key = provider_settings.get("api_key", "")
    if not api_key:
        return {
            "summary": "当前文本模型未配置 API Key",
            "reason": "当前文本模型未配置 API Key",
            "confidence": 0.0,
            "steps": [],
            "parser": "heuristic",
        }

    provider = get_provider(provider_id, provider_settings)
    payload = provider.generate_json(
        api_key=api_key,
        model=model_id,
        system_prompt=CHAT_SYSTEM_PROMPT,
        user_prompt=json.dumps(
            {
                "user_message": message,
                "task": {
                    "task_id": task.get("task_id"),
                    "task_name": task.get("task_name"),
                    "project_background": task.get("project_background", ""),
                    "style_requirements": task.get("style_requirements", ""),
                },
                "item": {
                    "item_id": item.get("item_id"),
                    "status": item.get("status"),
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "category": item.get("category", ""),
                    "extra_context": item.get("extra_context", ""),
                    "current_versions": item.get("current_versions", {}),
                    "runtime_overrides": item.get("runtime_overrides", {}),
                    "model_overrides": item.get("model_overrides", {}),
                },
                "available_models": _available_model_context(settings),
                "allowed_commands": ALLOWED_COMMANDS,
            },
            ensure_ascii=False,
        ),
    )
    plan = _validate_plan(payload)
    plan["parser"] = f"llm:{provider_id}"
    plan["provider"] = provider_id
    plan["model"] = model_id
    return plan


def _match_model(settings: dict, *, step: str, provider: str | None, query: str) -> tuple[str, str]:
    query_text = (query or "").strip().lower()
    if not query_text:
        raise ValueError("未提供模型名")
    candidates = provider_models_for_stage(settings, step)
    scored: list[tuple[int, dict]] = []
    for row in candidates:
        provider_label = provider_label_for(settings, row["provider"]).lower()
        if provider and provider != row["provider"] and provider.lower() not in provider_label:
            continue
        haystack = " ".join(
            [
                row["provider"].lower(),
                provider_label,
                row["model"].lower(),
                str(row.get("label", "")).lower(),
            ]
        )
        if query_text == row["model"].lower():
            scored.append((0, row))
        elif query_text in haystack:
            scored.append((1, row))
    if not scored:
        raise ValueError(f"没有找到匹配的模型：{query}")
    scored.sort(key=lambda item: item[0])
    matched = scored[0][1]
    return matched["provider"], matched["model"]


def _ensure_step_ready(task_id: str, item_id: str, target_step: str, *, source: str) -> None:
    while True:
        item = load_item(task_id, item_id)
        status = item["status"]
        if target_step == STEP_BRIEF_GENERATION:
            return
        if target_step == STEP_IMAGE_PROMPT:
            if status in {"brief_approved", "prompt_generated", "prompt_approved", "image_generating", "image_generated", "completed"}:
                return
            if status == "draft":
                run_step(task_id, item_id, STEP_BRIEF_GENERATION, source=source)
                continue
            if status == "brief_generated":
                approve_step(task_id, item_id, STEP_BRIEF_GENERATION, source=source)
                continue
            return
        if target_step == STEP_IMAGE_GENERATION:
            if status in {"prompt_approved", "image_generating", "image_generated", "completed"}:
                return
            if status == "draft":
                run_step(task_id, item_id, STEP_BRIEF_GENERATION, source=source)
                continue
            if status == "brief_generated":
                approve_step(task_id, item_id, STEP_BRIEF_GENERATION, source=source)
                continue
            if status == "brief_approved":
                run_step(task_id, item_id, STEP_IMAGE_PROMPT, source=source)
                continue
            if status == "prompt_generated":
                approve_step(task_id, item_id, STEP_IMAGE_PROMPT, source=source)
                continue
            return
        return


def execute_chat_plan(task_id: str, item_id: str, plan: dict, *, source: str = "chat") -> dict:
    results = []
    last_status = None
    for row in plan.get("steps", []):
        command = row["command"]
        args = row.get("args", {})
        if command == "approve_current_step":
            item = load_item(task_id, item_id)
            status = item["status"]
            if status == "brief_generated":
                result = approve_step(task_id, item_id, STEP_BRIEF_GENERATION, source=source)
            elif status == "prompt_generated":
                result = approve_step(task_id, item_id, STEP_IMAGE_PROMPT, source=source)
            elif status == "image_generating":
                result = poll_image_generation(task_id, item_id, source=source)
            elif status == "image_generated":
                result = approve_step(task_id, item_id, STEP_IMAGE_GENERATION, source=source)
            else:
                raise ValueError("当前状态没有可直接通过的步骤")
        elif command == "run_step":
            step = _normalize_step(args.get("step"))
            if step not in ALLOWED_STEPS:
                raise ValueError(f"非法步骤：{args.get('step')}")
            _ensure_step_ready(task_id, item_id, step, source=source)
            result = run_step(task_id, item_id, step, source=source)
        elif command == "poll_image_generation":
            result = poll_image_generation(task_id, item_id, source=source)
        elif command == "rollback_step":
            step = _normalize_step(args.get("step"))
            if step not in {STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT}:
                raise ValueError("只允许回退到设计说明或出图指令")
            result = rollback_step(task_id, item_id, step, source=source)
        elif command == "set_current_version":
            step = _normalize_step(args.get("step"))
            version = args.get("version")
            if step not in ALLOWED_STEPS or not version:
                raise ValueError("切换版本需要 step 和 version")
            result = set_current_version(task_id, item_id, step, str(version), source=source)
        elif command == "update_item_fields":
            result_item = update_item(
                task_id,
                item_id,
                title=args.get("title"),
                description=args.get("description"),
                category=args.get("category"),
                extra_context=args.get("extra_context"),
            )
            result = {"status": result_item.get("status"), "item_id": item_id, "command": command}
        elif command == "update_item_runtime":
            result_item = update_item(
                task_id,
                item_id,
                image_aspect_ratio=args.get("image_aspect_ratio"),
                image_resolution=args.get("image_resolution"),
            )
            result = {"status": result_item.get("status"), "item_id": item_id, "command": command}
        elif command == "set_stage_model":
            global_settings = load_global_settings()
            step = _normalize_step(args.get("step"))
            if step not in ALLOWED_STEPS:
                raise ValueError(f"非法步骤：{args.get('step')}")
            provider_query = args.get("provider")
            model_query = args.get("model") or args.get("model_query")
            provider_id, model_id = _match_model(
                global_settings,
                step=step,
                provider=provider_query,
                query=str(model_query or ""),
            )
            result_item = update_item_model_override(
                task_id,
                item_id,
                step,
                provider=provider_id,
                model=model_id,
            )
            result = {
                "status": result_item.get("status"),
                "item_id": item_id,
                "command": command,
                "provider": provider_id,
                "model": model_id,
            }
        else:
            raise ValueError(f"Unsupported chat command: {command}")
        results.append({"command": command, "args": args, "result": result})
        last_status = result.get("status", last_status)
    return {
        "status": last_status or load_item(task_id, item_id).get("status"),
        "steps_executed": len(results),
        "results": results,
    }
