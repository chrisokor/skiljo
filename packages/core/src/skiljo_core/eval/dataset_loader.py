"""Dataset loader for the Inspect eval harness (plan #57).

Turns the labeled `data/eval/{train,dev}/NN_slug.{policy.txt,skill.yaml}` pairs
(see `data/eval/README.md`) into an Inspect-compatible dataset of `Sample`s, so
`ExtractionEval`/`SimulationEval`/`E2EEval` (`extraction.py`/`simulation.py`/
`e2e.py`) can run against the real 60-example corpus instead of the single
vacuous dummy sample Inspect supplies for `dataset=None`.

**What this activates, and what it doesn't.** Wiring a real dataset makes
`extraction_recall` genuinely measured for the first time: `expected` (parsed
from `Sample.target`) is now the real hand-labeled rule set for each of the 30
train / 15 dev examples, rather than an empty dict Inspect fills in for the
dummy sample. `actual` is still `state.metadata.get("actual_spec", {})`
(see `extraction.py`), and nothing populates that key yet -- no "solver" step
calls `run_extraction_pipeline()` per sample and writes its output into task
state. So immediately after this change, `extraction_recall` against a real
model run will score genuinely low (typically 0.0, since `actual` stays `{}`)
rather than vacuously 1.0. That is the intended, honest consequence of closing
half the gap `docs/evals.md` describes (dataset landed, solver still doesn't
exist) -- not a bug in this loader. `citation_resolution` is unaffected (it
only reads `actual`, which is still empty, so it stays vacuously 1.0, keeping
the "citation resolution must stay at 100%" invariant intact).

`SimulationEval`/`E2EEval` reuse this same loader (there is no separate
ticket-level simulation ground truth in `data/eval/` yet -- only policy text
and a hand-labeled `Skill` spec per example). The `Sample.target` JSON this
loader builds includes `expected_e2e_accuracy` (read from a
`ground_truth_e2e_accuracy` field that no real `*.skill.yaml` file currently
sets, so it defaults to `0.0` for every real example today -- another honest,
documented gap, not a hidden default masking real data) but has no `results`
or `planted_divergence_ids` keys, so `simulation_match_rate` and the
contradiction precision/recall scorers keep hitting their vacuous-1.0
fallback paths (see `simulation.py`) until ticket-level ground truth is added
to the eval corpus. Wiring them here still activates the real 30/15-example
corpus size for those suites rather than a single dummy sample -- it's an
honest partial step, not a claim that simulation/e2e metrics are now
meaningful.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import yaml
from inspect_ai.dataset import Sample

# data/eval/test/ is the held-out set (CLAUDE.md system invariant 5): never
# read, printed, summarized, or tuned against outside of CI. Loading it here
# would make it trivially easy to do all three by accident, so it's blocked
# at the source rather than relying solely on the `.CODEOWNERS` speed bump.
_FORBIDDEN_SPLITS = {"test"}


@dataclass
class ExtractionExample:
    """One labeled `data/eval/{split}/NN_slug.*` pair.

    `expected_rules` flattens all three decision zones
    (`deterministic`/`llm_assisted`/`human_only`) of the hand-labeled
    `*.skill.yaml` into a single list of rule dicts -- matching how
    `extraction.py`'s `_iter_rules`/`_rule_key` already treat rules as
    zone-agnostic for recall purposes (a rule extracted into the "wrong"
    zone still counts as found). `expected_e2e_accuracy` reads a
    `ground_truth_e2e_accuracy` field from the skill YAML that no real
    example currently sets (see module docstring); it defaults to `0.0`.
    """

    policy_text: str
    expected_rules: list[dict[str, Any]]
    expected_e2e_accuracy: float

    @property
    def input(self) -> dict[str, Any]:
        """Dict view used by tests/callers that want sample input by key."""
        return {"policy_text": self.policy_text}

    @property
    def target(self) -> dict[str, Any]:
        """Dict view of this example's ground truth, keyed by field name.

        Distinct from the JSON string `ExtractionDataset.__iter__` builds for
        the Inspect `Sample.target` (which nests `expected_rules` under
        `decision_zones` so `extraction.py`'s `_iter_rules` can walk it) --
        this property is a flat, ergonomic view for direct attribute access.
        """
        return {
            "expected_rules": self.expected_rules,
            "expected_e2e_accuracy": self.expected_e2e_accuracy,
        }


@dataclass
class ExtractionDataset:
    """Minimal Inspect dataset: anything with `__iter__` + `__len__` over
    `Sample`s works as a `Task(dataset=...)` value -- Inspect wraps it in a
    `MemoryDataset` internally. No need to implement the full `Dataset`
    Sequence protocol (`__getitem__`, `shuffle`, `filter`, ...).
    """

    examples: list[ExtractionExample] = field(default_factory=list)

    def __iter__(self) -> Iterator[Sample]:
        for ex in self.examples:
            target = {
                "decision_zones": {
                    "deterministic": ex.expected_rules,
                    "llm_assisted": [],
                    "human_only": [],
                },
                "expected_e2e_accuracy": ex.expected_e2e_accuracy,
            }
            yield Sample(
                input=ex.policy_text,
                target=json.dumps(target),
            )

    def __len__(self) -> int:
        return len(self.examples)


def _flatten_zone_rules(skill_yaml: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a hand-labeled skill YAML's three decision zones into one list.

    Deliberately standalone rather than importing `extraction._iter_rules`:
    `extraction.py` imports this module (to wire the dataset into
    `ExtractionEval`), so importing back from `extraction.py` here would be
    circular. The traversal is intentionally identical.
    """
    zones = skill_yaml.get("decision_zones") or {}
    rules: list[dict[str, Any]] = []
    for zone_name in ("deterministic", "llm_assisted", "human_only"):
        rules.extend(zones.get(zone_name) or [])
    return rules


def load_extraction_dataset(split: str = "train") -> ExtractionDataset:
    """Load labeled extraction examples from `data/eval/{split}/` on disk.

    Pairs each `NN_slug.policy.txt` with its `NN_slug.skill.yaml` (skipping
    any policy file with no matching skill file) and returns one
    `ExtractionExample` per pair. `split="train"` yields 30 examples,
    `split="dev"` yields 15 (per `data/eval/README.md`'s committed split).

    Args:
        split: Which `data/eval/` subdirectory to load. `"test"` is rejected
            (CLAUDE.md system invariant 5 -- the held-out set is never read
            outside of CI, including by this loader).

    Raises:
        ValueError: if `split` is `"test"`.
    """
    if split in _FORBIDDEN_SPLITS:
        raise ValueError(
            f"split={split!r} is off-limits: data/eval/test/ is the held-out set "
            "(CLAUDE.md system invariant 5) and must never be read, printed, or "
            "tuned against outside of CI. Use split='train' or split='dev'."
        )

    eval_dir = Path(__file__).resolve().parents[5] / "data" / "eval" / split
    examples: list[ExtractionExample] = []

    for policy_file in sorted(eval_dir.glob("*.policy.txt")):
        slug = policy_file.stem.replace(".policy", "")
        skill_file = eval_dir / f"{slug}.skill.yaml"
        if not skill_file.exists():
            continue

        policy_text = policy_file.read_text()
        skill_yaml = yaml.safe_load(skill_file.read_text()) or {}

        examples.append(
            ExtractionExample(
                policy_text=policy_text,
                expected_rules=_flatten_zone_rules(skill_yaml),
                expected_e2e_accuracy=float(skill_yaml.get("ground_truth_e2e_accuracy", 0.0)),
            )
        )

    return ExtractionDataset(examples=examples)
