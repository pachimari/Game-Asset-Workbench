from __future__ import annotations

import json
import re

from .config import STEP_BRIEF_GENERATION, STEP_IMAGE_GENERATION, STEP_IMAGE_PROMPT
from .pipeline import approve_step, rollback_step, run_step, set_current_version
from .providers.registry import get_provider
from .settings import resolve_stage_selection
from .storage import list_artifacts, load_item, load_task


ALLOWED_ACTIONS = {
    "rerun_brief_generation",
    "rerun_prompt",
    "rerun_image",
    "rollback_to_brief",
    "rollback_to_prompt",
    "approve_current_step",
    "unsupported",
}


CHAT_SYSTEM_PROMPT = """你是游戏图标工作台里的受控动作路由器。
你的任务不是自由回答，而是把用户指令解析成结构化 JSON。
只允许输出以下 action 之一：
- rerun_brief_generation
- rerun_prompt
- rerun_image
- rollback_to_brief
- rollback_to_prompt
- approve_current_step
- unsupported

返回 JSON 对象，字段必须包含：
- action: string
- reason: string
- confidence: number

如果用户意图不明确，或者超出允许动作，请返回 unsupported。
不要输出解释文本，不要输出 markdown。"""


def _latest_version(task_id: str, item_id: str, step: str) -> str | None:
    artifacts = list_artifacts(task_id, item_id, step)
    if not artifacts:
        return None
    return artifacts[-1]["version"]


def _heuristic_parse(message: str) -> dict | None:
    text = message.strip().lower()
    if not text:
        return None

    if any(token in text for token in ["返回设计说明", "回到设计说明", "回退设计说明", "rollback brief"]):
        return {"action": "rollback_to_brief", "reason": "命中设计说明回退关键词", "confidence": 0.98}
    if any(token in text for token in ["返回出图指令", "回退出图指令", "回到出图指令", "rollback prompt"]):
        return {"action": "rollback_to_prompt", "reason": "命中出图指令回退关键词", "confidence": 0.98}
    if re.search(r"(重跑|重新生成).*(设计说明|需求整理|brief)", text):
        return {"action": "rerun_brief_generation", "reason": "命中设计说明重跑关键词", "confidence": 0.98}
    if re.search(r"(重跑|重新生成).*(出图指令|prompt)", text):
        return {"action": "rerun_prompt", "reason": "命中出图指令重跑关键词", "confidence": 0.98}
    if re.search(r"(重跑|重新生成).*(候选图|出图|图片)", text):
        return {"action": "rerun_image", "reason": "命中候选图重跑关键词", "confidence": 0.95}
    if any(token in text for token in ["通过", "确认", "采纳", "继续"]):
        return {"action": "approve_current_step", "reason": "命中继续/通过关键词", "confidence": 0.82}
    return None


def parse_chat_action(task: dict, item: dict, settings: dict, message: str) -> dict:
    heuristic = _heuristic_parse(message)
    if heuristic:
        return {**heuristic, "parser": "heuristic"}

    selected_runtime = resolve_stage_selection(task, item, settings, STEP_IMAGE_PROMPT)
    provider_id = selected_runtime["provider"]
    model_id = selected_runtime["model"]

    if provider_id == "mock":
        return {
            "action": "unsupported",
            "reason": "当前未配置真实文本模型，且本地规则没有识别出指令",
            "confidence": 0.0,
            "parser": "heuristic",
        }

    provider_settings = settings.get("providers", {}).get(provider_id, {})
    api_key = provider_settings.get("api_key", "")
    if not api_key:
        return {
            "action": "unsupported",
            "reason": "当前文本模型未配置 API Key",
            "confidence": 0.0,
            "parser": "heuristic",
        }

    provider = get_provider(provider_id)
    payload = provider.generate_json(
        api_key=api_key,
        model=model_id,
        system_prompt=CHAT_SYSTEM_PROMPT,
        user_prompt=json.dumps(
            {
                "item_status": item.get("status"),
                "user_message": message,
                "allowed_actions": sorted(ALLOWED_ACTIONS),
            },
            ensure_ascii=False,
        ),
    )
    action = str(payload.get("action") or "unsupported")
    if action not in ALLOWED_ACTIONS:
        action = "unsupported"
    return {
        "action": action,
        "reason": str(payload.get("reason") or "模型未返回原因"),
        "confidence": float(payload.get("confidence") or 0.0),
        "parser": f"llm:{provider_id}",
        "provider": provider_id,
        "model": model_id,
    }


def execute_chat_action(task_id: str, item_id: str, action: str, *, source: str = "chat") -> dict:
    task = load_task(task_id)
    item = load_item(task_id, item_id)
    status = item["status"]

    if action == "approve_current_step":
        if status == "brief_generated":
            return approve_step(task_id, item_id, STEP_BRIEF_GENERATION, source=source)
        if status == "prompt_generated":
            return approve_step(task_id, item_id, STEP_IMAGE_PROMPT, source=source)
        if status == "image_generated":
            return approve_step(task_id, item_id, STEP_IMAGE_GENERATION, source=source)
        raise ValueError("当前状态没有可直接通过的步骤")

    if action == "rollback_to_brief":
        return rollback_step(task_id, item_id, STEP_BRIEF_GENERATION, source=source)

    if action == "rollback_to_prompt":
        return rollback_step(task_id, item_id, STEP_IMAGE_PROMPT, source=source)

    if action == "rerun_brief_generation":
        latest_brief = _latest_version(task_id, item_id, STEP_BRIEF_GENERATION)
        if status not in {"draft", "brief_generated"} and latest_brief:
            set_current_version(task_id, item_id, STEP_BRIEF_GENERATION, latest_brief, source=source)
        return run_step(task_id, item_id, STEP_BRIEF_GENERATION, source=source)

    if action == "rerun_prompt":
        item = load_item(task_id, item_id)
        if item["status"] == "brief_generated":
            approve_step(task_id, item_id, STEP_BRIEF_GENERATION, source=source)
            item = load_item(task_id, item_id)
        latest_prompt = _latest_version(task_id, item_id, STEP_IMAGE_PROMPT)
        if item["status"] not in {"brief_approved", "prompt_generated"} and latest_prompt:
            set_current_version(task_id, item_id, STEP_IMAGE_PROMPT, latest_prompt, source=source)
            item = load_item(task_id, item_id)
        if item["status"] == "brief_generated":
            approve_step(task_id, item_id, STEP_BRIEF_GENERATION, source=source)
        return run_step(task_id, item_id, STEP_IMAGE_PROMPT, source=source)

    if action == "rerun_image":
        item = load_item(task_id, item_id)
        if item["status"] == "prompt_generated":
            approve_step(task_id, item_id, STEP_IMAGE_PROMPT, source=source)
            item = load_item(task_id, item_id)
        latest_image = _latest_version(task_id, item_id, STEP_IMAGE_GENERATION)
        if item["status"] not in {"prompt_approved", "image_generated"} and latest_image:
            set_current_version(task_id, item_id, STEP_IMAGE_GENERATION, latest_image, source=source)
            item = load_item(task_id, item_id)
        if item["status"] not in {"prompt_approved", "image_generated"}:
            prompt_version = item.get("current_versions", {}).get(STEP_IMAGE_PROMPT)
            if prompt_version:
                set_current_version(task_id, item_id, STEP_IMAGE_PROMPT, prompt_version, source=source)
                approve_step(task_id, item_id, STEP_IMAGE_PROMPT, source=source)
        return run_step(task_id, item_id, STEP_IMAGE_GENERATION, source=source)

    raise ValueError(f"Unsupported chat action: {action}")
