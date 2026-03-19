from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    try:
        from streamlit.web import cli as stcli
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Streamlit is not installed. Install it with: "
            "python3 -m pip install 'streamlit>=1.36'"
        ) from exc

    app_path = Path(__file__).with_name("ui.py")
    sys.argv = ["streamlit", "run", str(app_path)]
    return stcli.main()
