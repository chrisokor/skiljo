#!/usr/bin/env python3
"""CI entry point for refreshing the eval baseline on merge to main (plan #58).

Thin wrapper around ``skiljo_core.eval.baseline`` so it can be invoked directly as
``python scripts/update_baseline.py`` (or ``uv run python scripts/update_baseline.py``)
from GitHub Actions. See that module for the refresh logic and its tests.

Usage:
    python scripts/update_baseline.py
    python scripts/update_baseline.py --model anthropic/claude-sonnet-4-6
"""

from __future__ import annotations

import sys

from skiljo_core.eval.baseline import main

if __name__ == "__main__":
    sys.exit(main())
