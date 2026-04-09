"""Pytest configuration shared across test modules."""

from __future__ import annotations

import sys
from pathlib import Path


# Ensure project root is importable for `from app ...` in all pytest entry modes.
ROOT = Path(__file__).resolve().parents[1]
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)
