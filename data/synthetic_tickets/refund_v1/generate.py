#!/usr/bin/env python
"""One-off script: generate refund_v1 synthetic ticket batch."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "packages/core/src"))

from skiljo_core.schemas.skill_schema import Skill
from skiljo_core.simulation.generator import (
    DivergenceSpec,
    TicketFieldRanges,
    generate_ticket_batch,
)

SCRIPT_DIR = Path(__file__).parent

skill_path = SCRIPT_DIR / "skill.json"
div_path = SCRIPT_DIR / "divergence_spec.json"
out_path = SCRIPT_DIR / "tickets.json"

skill = Skill.model_validate_json(skill_path.read_text())
div_raw = json.loads(div_path.read_text())
divergences = [DivergenceSpec.model_validate(d) for d in div_raw]

# Use a wider refund_amount range so escalate_to_finance rule fires (>500),
# and include near-threshold amounts (100–120) for the near_threshold_leniency divergence.
ranges = TicketFieldRanges(
    refund_amount_min=0.0,
    refund_amount_max=600.0,
)

tickets = generate_ticket_batch(skill, divergences, count=100, seed=42, ranges=ranges)
out_path.write_text(json.dumps([t.model_dump(mode="json") for t in tickets], indent=2))
print(f"Generated {len(tickets)} tickets -> {out_path}")
