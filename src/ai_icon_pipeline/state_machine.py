from __future__ import annotations

from .config import (
    STATUS_ARCHIVED,
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


GENERATION_RULES = {
    STEP_BRIEF_GENERATION: {
        "allowed_statuses": {STATUS_DRAFT, STATUS_BRIEF_GENERATED},
        "next_status": STATUS_BRIEF_GENERATED,
    },
    STEP_IMAGE_PROMPT: {
        "allowed_statuses": {STATUS_BRIEF_APPROVED, STATUS_PROMPT_GENERATED},
        "next_status": STATUS_PROMPT_GENERATED,
    },
    STEP_IMAGE_GENERATION: {
        "allowed_statuses": {STATUS_PROMPT_APPROVED, STATUS_IMAGE_GENERATED, STATUS_IMAGE_GENERATING, STATUS_FAILED},
        "next_status": STATUS_IMAGE_GENERATED,
    },
}

APPROVAL_RULES = {
    STEP_BRIEF_GENERATION: {
        "required_status": STATUS_BRIEF_GENERATED,
        "next_status": STATUS_BRIEF_APPROVED,
    },
    STEP_IMAGE_PROMPT: {
        "required_status": STATUS_PROMPT_GENERATED,
        "next_status": STATUS_PROMPT_APPROVED,
    },
    STEP_IMAGE_GENERATION: {
        "required_status": STATUS_IMAGE_GENERATED,
        "next_status": STATUS_COMPLETED,
    },
}

TERMINAL_STATUSES = {STATUS_COMPLETED, STATUS_FAILED, STATUS_ARCHIVED}


class StateMachineError(ValueError):
    """Raised when an item transition is invalid."""


def validate_generation(step: str, status: str) -> str:
    rule = GENERATION_RULES[step]
    if status not in rule["allowed_statuses"]:
        raise StateMachineError(
            f"Cannot run step '{step}' while item status is '{status}'"
        )
    return rule["next_status"]


def validate_approval(step: str, status: str) -> str:
    rule = APPROVAL_RULES[step]
    if status != rule["required_status"]:
        raise StateMachineError(
            f"Cannot approve step '{step}' while item status is '{status}'"
        )
    return rule["next_status"]
