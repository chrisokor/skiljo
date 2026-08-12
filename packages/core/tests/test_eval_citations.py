from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
EVAL_ROOT = REPO_ROOT / "data" / "eval"


def _load_citation_script() -> ModuleType:
    script_path = REPO_ROOT / "scripts" / "add_eval_citations.py"
    spec = importlib.util.spec_from_file_location("add_eval_citations", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rules(split: str, filename: str) -> list[dict]:
    skill = yaml.safe_load((EVAL_ROOT / split / filename).read_text())
    zones = skill["decision_zones"]
    return [
        rule
        for zone in ("deterministic", "llm_assisted", "human_only")
        for rule in zones.get(zone, [])
    ]


@pytest.mark.parametrize(
    ("split", "filename", "rule_index", "required_evidence"),
    [
        (
            "dev",
            "03_amazon_ec2_dual_sla_claim.skill.yaml",
            0,
            ("SLA Credit Request", "second billing cycle"),
        ),
        (
            "dev",
            "03_amazon_ec2_dual_sla_claim.skill.yaml",
            1,
            ("Claims that omit required information", "denied"),
        ),
        (
            "dev",
            "12_shopify_plus_prepaid_fees_nonrefundable.skill.yaml",
            0,
            ("material breach", "forfeited", "no refund"),
        ),
        (
            "dev",
            "12_shopify_plus_prepaid_fees_nonrefundable.skill.yaml",
            1,
            ("uncured material breach", "prorated portion"),
        ),
        (
            "train",
            "30_github_marketplace_billing.skill.yaml",
            1,
            ("Upgrades", "take effect immediately", "prorated difference"),
        ),
    ],
)
def test_reviewed_eval_citations_include_rule_evidence(
    split: str,
    filename: str,
    rule_index: int,
    required_evidence: tuple[str, ...],
) -> None:
    quote = " ".join(
        _rules(split, filename)[rule_index]["citation"]["quoted_text"].split()
    )

    assert all(fragment in quote for fragment in required_evidence)


def test_google_credit_tier_citations_include_threshold_cap_and_claim_requirements() -> None:
    rules = _rules("train", "20_google_cloud_compute_sla.skill.yaml")

    for rule in rules[3:]:
        quote = rule["citation"]["quoted_text"]
        percentage = rule["action"].split("_percent", 1)[0].rsplit("_", 1)[-1]
        assert f"{percentage}% credit" in quote
        assert "50% of the amounts paid or payable" in quote
        assert "Google Cloud Console support portal" in quote


def test_reviewed_override_must_be_unique_in_policy_text() -> None:
    citation_script = _load_citation_script()

    with pytest.raises(ValueError, match="exactly once"):
        citation_script._reviewed_citation("same evidence", "same evidence\n\nsame evidence")
