"""Start the local rerank adapter service.

Usage:
    uv run python script/run_rerank_adapter.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rerank_adapter import main


if __name__ == "__main__":
    main()
