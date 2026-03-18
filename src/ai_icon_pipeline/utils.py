from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import base64

from .config import PLACEHOLDER_PNG_BASE64


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_placeholder_png(path: Path) -> None:
    ensure_dir(path.parent)
    path.write_bytes(base64.b64decode(PLACEHOLDER_PNG_BASE64))

