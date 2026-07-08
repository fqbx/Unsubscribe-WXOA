"""WeChat Official Account batch unsubscribe — entry point."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path when run as script
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    from src.gui.app import run_app

    config_path = ROOT / "config" / "default.yaml"
    run_app(config_path=str(config_path))


if __name__ == "__main__":
    main()
