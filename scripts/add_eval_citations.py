"""Add mechanically valid paragraph citations to train/dev eval skill YAML.

The candidate selector intentionally uses only words present in a rule's action
and predicate fields/values. It writes a full policy paragraph so the quote is
always an exact, reviewable source substring. Review the dry-run output before
using ``--write``; a low-confidence rule should receive an explicit override
rather than an invented citation.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

from skiljo_core.extraction.citation_validator import validate_citation
from skiljo_core.schemas.rule_schema import Citation


EVAL_ROOT = Path(__file__).resolve().parents[1] / "data" / "eval"
SPLITS = ("train", "dev")
IGNORED_TERMS = {
    "all",
    "any",
    "apply",
    "and",
    "approve",
    "customer",
    "is",
    "no",
    "not",
    "of",
    "or",
    "process",
    "request",
    "to",
    "the",
}

# Literal action/predicate overlap cannot rank these paraphrased rules. Each
# override is the narrowest full policy paragraph that supports the rule.
EVIDENCE_OVERRIDES = {
    (
        "train",
        "09_stripe_subscription_policy.skill.yaml",
        1,
    ): (
        "These terms do not limit any rights you may have under applicable law, including rights "
        "related to statutory refunds or consumer protection where required by applicable jurisdiction."
    ),
    (
        "train",
        "19_github_tos_payments.skill.yaml",
        1,
    ): (
        "User agrees to pay the fees in full, up front without deduction or setoff of any kind, "
        "in U.S. Dollars. User must pay the fees within thirty (30) days of the GitHub invoice "
        "date. Amounts payable under this Agreement are non-refundable, except as otherwise "
        "provided in this Agreement."
    ),
    (
        "train",
        "29_atlassian_cancellation_mechanics.skill.yaml",
        1,
    ): (
        "Free tier: If you cancel a free-tier product, deactivation is immediate upon\n"
        "cancellation \u2014 there is no grace period because no billing cycle applies."
    ),
}


def _terms(value: Any) -> set[str]:
    """Return meaningful lowercase terms from nested rule content."""
    if isinstance(value, dict):
        return set().union(*(_terms(item) for item in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_terms(item) for item in value)) if value else set()
    return {
        term
        for term in re.findall(r"[a-zA-Z0-9]+", str(value).lower())
        if len(term) > 1 and term not in IGNORED_TERMS
    }


def _paragraphs(policy_text: str) -> list[tuple[int, int, str]]:
    """Return non-empty policy paragraphs with full-document offsets."""
    paragraphs: list[tuple[int, int, str]] = []
    for match in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", policy_text, re.DOTALL):
        paragraphs.append((match.start(), match.end(), match.group()))
    return paragraphs


def _best_paragraph(
    rule: dict[str, Any], policy_text: str, override: str | None = None
) -> tuple[int, int, str, int]:
    """Select the paragraph with the strongest literal overlap with a rule."""
    if override is not None:
        start = policy_text.find(override)
        if start < 0:
            raise ValueError(f"Configured citation override was not found: {override!r}")
        return start, start + len(override), override, -1

    rule_terms = _terms(rule.get("action", "")) | _terms(rule.get("condition", {}))
    candidates: list[tuple[int, int, str, int]] = []
    for start, end, paragraph in _paragraphs(policy_text):
        paragraph_terms = _terms(paragraph)
        score = len(rule_terms & paragraph_terms)
        candidates.append((start, end, paragraph, score))
    if not candidates:
        raise ValueError("Policy contains no citeable text")
    return max(candidates, key=lambda candidate: candidate[3])


def _rules(skill: dict[str, Any]) -> list[dict[str, Any]]:
    zones = skill.get("decision_zones") or {}
    return [
        rule
        for zone in ("deterministic", "llm_assisted", "human_only")
        for rule in zones.get(zone, []) or []
    ]


def _write_citations(
    skill_file: Path, rules: list[dict[str, Any]], citations: list[Citation]
) -> None:
    """Insert citation mappings after existing action lines without reformatting YAML."""
    raw_skill = skill_file.read_text()
    actions = list(re.finditer(r"^(?P<indent>\s*)action:\s*(?P<action>\S.*?)\s*$", raw_skill, re.MULTILINE))
    if len(actions) != len(rules):
        raise ValueError(
            f"Found {len(actions)} action lines but {len(rules)} rules in {skill_file}"
        )

    replacements: list[tuple[int, str]] = []
    for action_match, rule, citation in zip(actions, rules, citations, strict=True):
        if action_match.group("action") != rule["action"]:
            raise ValueError(
                f"Action order mismatch in {skill_file}: "
                f"{action_match.group('action')!r} != {rule['action']!r}"
            )
        indent = action_match.group("indent")
        replacements.append(
            (
                action_match.end(),
                "\n"
                f"{indent}citation:\n"
                f"{indent}  span:\n"
                f"{indent}    start: {citation.span.start}\n"
                f"{indent}    end: {citation.span.end}\n"
                f"{indent}  quoted_text: {json.dumps(citation.quoted_text, ensure_ascii=True)}",
            )
        )

    for offset, insertion in reversed(replacements):
        raw_skill = raw_skill[:offset] + insertion + raw_skill[offset:]
    skill_file.write_text(raw_skill)


def add_citations(split: str, write: bool) -> tuple[int, list[str]]:
    """Generate and validate citations for every skill in one allowed split."""
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}, got {split!r}")

    updated = 0
    low_confidence: list[str] = []
    for policy_file in sorted((EVAL_ROOT / split).glob("*.policy.txt")):
        skill_file = policy_file.with_suffix("").with_suffix(".skill.yaml")
        policy_text = policy_file.read_text()
        skill = yaml.safe_load(skill_file.read_text()) or {}

        rules = _rules(skill)
        existing_citations = [rule.get("citation") for rule in rules]
        if any(existing_citations):
            if not all(existing_citations):
                raise ValueError(f"{skill_file} has only some rule citations")
            for existing_citation in existing_citations:
                validate_citation(Citation.model_validate(existing_citation), policy_text)
            print(f"{skill_file.name}: validated {len(rules)} existing citations")
            continue

        citations: list[Citation] = []
        for index, rule in enumerate(rules, start=1):
            override = EVIDENCE_OVERRIDES.get((split, skill_file.name, index))
            start, end, quote, score = _best_paragraph(rule, policy_text, override)
            citation = Citation.model_validate(
                {"span": {"start": start, "end": end}, "quoted_text": quote}
            )
            validate_citation(citation, policy_text)
            citations.append(citation)
            if score == 0:
                low_confidence.append(f"{skill_file.name} rule {index}: {rule['action']}")
            print(
                f"{skill_file.name} rule {index} score={score}: "
                f"[{start}, {end}) {rule['action']}"
            )

        if write:
            _write_citations(skill_file, rules, citations)
            updated += 1

    return updated, low_confidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write generated citations to YAML")
    parser.add_argument("--split", choices=SPLITS, action="append", default=[])
    args = parser.parse_args()

    splits = tuple(args.split) or SPLITS
    updated = 0
    low_confidence: list[str] = []
    for split in splits:
        split_updated, split_low_confidence = add_citations(split, args.write)
        updated += split_updated
        low_confidence.extend(split_low_confidence)

    if low_confidence:
        raise SystemExit("Low-confidence citations:\n" + "\n".join(low_confidence))
    print(f"Validated {updated if args.write else 'all'} {', '.join(splits)} skill files")


if __name__ == "__main__":
    main()
