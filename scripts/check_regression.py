#!/usr/bin/env python3
"""CI entry point for eval regression gating (plan #52).

Thin wrapper around ``skiljo_core.eval.regression`` so it can be invoked directly as
``python scripts/check_regression.py ...`` (or ``uv run python scripts/check_regression.py
...``) from GitHub Actions. See that module for the comparison logic and its tests.

Usage:
    python scripts/check_regression.py \\
        --current eval-results.json \\
        --baseline-ref origin/main \\
        --baseline-path data/eval/baseline_metrics.json \\
        --check extraction_recall=-0.02 \\
        --check citation_resolution=0:min=1.0
"""

from __future__ import annotations

import sys

from skiljo_core.eval.regression import main

if __name__ == "__main__":
    sys.exit(main())
