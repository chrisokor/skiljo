"""Cross-document contradiction detection (scope A3).

Given rules extracted from two or more policy *documents* belonging to the
same company (e.g. a Terms of Service and a help-center article), find
pairs of rules that govern the same underlying decision — the "decision
surface" — but prescribe conflicting actions.

This is distinct from same-document contradiction detection
(``skiljo_core.simulation.contradictions``), which clusters *simulated
ticket outcomes* against a single written policy to find where practice
diverges from the document. Here there is no simulation: we are aligning
written rules across *different* documents and flagging outright
disagreements between them (e.g. Shopify's ToS says "no refunds" while its
help center describes a case-by-case review window).

Alignment is LLM-assisted (each rule is assigned a decision-surface label so
that same-topic rules from different documents can be grouped), but
conflicts are only ever reported when a *mechanical* check also confirms
the two rules actually prescribe different actions. This mechanical gate
exists so a hallucinated "conflict" from the LLM step can never produce a
contradiction on its own — see ``_check_conflict`` and its call site in
``detect_cross_document_contradictions``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from skiljo_core import config
from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.rule_schema import (
    Condition,
    DeterministicRule,
    HumanOnlyRule,
    LLMAssistedRule,
    Operator,
    Predicate,
)
from skiljo_core.schemas.skill_schema import Skill

AnyRule = DeterministicRule | LLMAssistedRule | HumanOnlyRule
ZoneName = Literal["deterministic", "llm_assisted", "human_only"]

DECISION_SURFACE_PROMPT_V1 = """You are aligning policy rules extracted from different documents belonging \
to the same company, so that rules governing the same underlying business \
decision can be compared.

Classify which decision surface the following rule governs. Use a short \
snake_case label (e.g. "refund_eligibility", "sla_credit", \
"subscription_cancellation") that is stable across documents: two rules \
about the same underlying question must receive the exact same label, even \
if their conditions or wording differ.

Rule action: {action}
Rule condition: {condition_json}
"""

CONFLICT_CHECK_PROMPT_V1 = """Two policy rules, extracted from different documents belonging to the same \
company, have been aligned onto the same decision surface: "{surface}".

Rule A (from document "{policy_a}"):
  condition: {condition_a}
  action: {action_a}

Rule B (from document "{policy_b}"):
  condition: {condition_b}
  action: {action_b}

Determine whether a real-world case could reasonably fall under both rules' \
conditions, yet the two documents prescribe genuinely different actions for \
it (a true policy-vs-policy contradiction) — as opposed to the rules simply \
covering non-overlapping situations or using different wording for the same \
outcome.
"""


class DecisionSurfaceClassification(BaseModel):
    decision_surface: str


class ConflictCheck(BaseModel):
    is_conflict: bool
    rationale: str


@dataclass
class PolicyDocument:
    """One extracted skill, tagged with the source document it came from."""

    policy_id: str
    skill: Skill


@dataclass
class RuleRef:
    """A single rule plus enough provenance to cite it unambiguously."""

    policy_id: str
    zone: ZoneName
    index: int
    action: str
    condition: Condition


@dataclass
class CrossDocumentCitation:
    policy_id: str
    zone: ZoneName
    rule_index: int
    action: str


@dataclass
class CrossDocumentContradiction:
    decision_surface: str
    policy_1: str
    policy_2: str
    action_1: str
    action_2: str
    rationale: str
    citation_1: CrossDocumentCitation
    citation_2: CrossDocumentCitation


def _rule_refs(policy: PolicyDocument) -> list[RuleRef]:
    refs: list[RuleRef] = []
    zones: list[tuple[ZoneName, list[AnyRule]]] = [
        ("deterministic", list(policy.skill.decision_zones.deterministic)),
        ("llm_assisted", list(policy.skill.decision_zones.llm_assisted)),
        ("human_only", list(policy.skill.decision_zones.human_only)),
    ]
    for zone_name, rules in zones:
        for index, rule in enumerate(rules):
            refs.append(
                RuleRef(
                    policy_id=policy.policy_id,
                    zone=zone_name,
                    index=index,
                    action=rule.action,
                    condition=rule.condition,
                )
            )
    return refs


def _predicate_fields(condition: Condition) -> set[str]:
    fields: set[str] = set()
    for clauses in (condition.all, condition.any):
        for clause in clauses or []:
            if isinstance(clause.root, Predicate):
                fields.add(clause.root.field)
            else:
                fields.update(_predicate_fields(clause.root))
    return fields


def _conjunctive_predicates(condition: Condition) -> list[Predicate] | None:
    """Flatten pure conjunctions; return None when an OR requires real solving."""
    if condition.any is not None:
        return None
    predicates: list[Predicate] = []
    for clause in condition.all or []:
        if isinstance(clause.root, Predicate):
            predicates.append(clause.root)
            continue
        nested = _conjunctive_predicates(clause.root)
        if nested is None:
            return None
        predicates.extend(nested)
    return predicates


def _same_value(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return left == right


def _numeric_interval_is_empty(predicates: list[Predicate]) -> bool:
    lower: tuple[float, bool] | None = None
    upper: tuple[float, bool] | None = None

    def update_lower(value: float, inclusive: bool) -> None:
        nonlocal lower
        if lower is None or value > lower[0]:
            lower = (value, inclusive)
        elif value == lower[0]:
            lower = (value, lower[1] and inclusive)

    def update_upper(value: float, inclusive: bool) -> None:
        nonlocal upper
        if upper is None or value < upper[0]:
            upper = (value, inclusive)
        elif value == upper[0]:
            upper = (value, upper[1] and inclusive)

    for predicate in predicates:
        value = predicate.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        numeric_value = float(value)
        if predicate.op == Operator.gt:
            update_lower(numeric_value, False)
        elif predicate.op == Operator.gte:
            update_lower(numeric_value, True)
        elif predicate.op == Operator.lt:
            update_upper(numeric_value, False)
        elif predicate.op == Operator.lte:
            update_upper(numeric_value, True)
        elif predicate.op == Operator.eq:
            update_lower(numeric_value, True)
            update_upper(numeric_value, True)

    if lower is None or upper is None:
        return False
    if lower[0] > upper[0]:
        return True
    return lower[0] == upper[0] and not (lower[1] and upper[1])


def _field_constraints_are_disjoint(
    predicates_a: list[Predicate], predicates_b: list[Predicate]
) -> bool:
    equalities_a = [p.value for p in predicates_a if p.op == Operator.eq]
    equalities_b = [p.value for p in predicates_b if p.op == Operator.eq]
    if equalities_a and equalities_b and not any(
        _same_value(left, right)
        for left in equalities_a
        for right in equalities_b
    ):
        return True

    return _numeric_interval_is_empty([*predicates_a, *predicates_b])


def _conditions_may_overlap(condition_a: Condition, condition_b: Condition) -> bool:
    shared_fields = _predicate_fields(condition_a) & _predicate_fields(condition_b)
    if not shared_fields:
        return False

    predicates_a = _conjunctive_predicates(condition_a)
    predicates_b = _conjunctive_predicates(condition_b)
    if predicates_a is None or predicates_b is None:
        return True

    for field_name in shared_fields:
        field_predicates_a = [p for p in predicates_a if p.field == field_name]
        field_predicates_b = [p for p in predicates_b if p.field == field_name]
        if _field_constraints_are_disjoint(field_predicates_a, field_predicates_b):
            return False
    return True


def _assign_decision_surface(llm_client: LLMClient, ref: RuleRef, model: str) -> str:
    prompt = DECISION_SURFACE_PROMPT_V1.format(
        action=ref.action,
        condition_json=ref.condition.model_dump_json(),
    )
    response = llm_client.generate_structured(
        prompt=prompt,
        schema=DecisionSurfaceClassification,
        model=model,
        prompt_version="decision_surface_v1",
    )
    return response.data.decision_surface


def _check_conflict(
    llm_client: LLMClient,
    ref_a: RuleRef,
    ref_b: RuleRef,
    surface: str,
    model: str,
) -> ConflictCheck:
    prompt = CONFLICT_CHECK_PROMPT_V1.format(
        surface=surface,
        policy_a=ref_a.policy_id,
        condition_a=ref_a.condition.model_dump_json(),
        action_a=ref_a.action,
        policy_b=ref_b.policy_id,
        condition_b=ref_b.condition.model_dump_json(),
        action_b=ref_b.action,
    )
    response = llm_client.generate_structured(
        prompt=prompt,
        schema=ConflictCheck,
        model=model,
        prompt_version="cross_document_conflict_v1",
    )
    return response.data


def _citation(ref: RuleRef) -> CrossDocumentCitation:
    return CrossDocumentCitation(
        policy_id=ref.policy_id,
        zone=ref.zone,
        rule_index=ref.index,
        action=ref.action,
    )


def detect_cross_document_contradictions(
    policies: list[PolicyDocument],
    llm_client: LLMClient,
    model: str = config.DEFAULT_MODEL,
) -> list[CrossDocumentContradiction]:
    """Find conflicting rules across two or more policy documents.

    Alignment (grouping rules onto a shared "decision surface") is
    LLM-assisted. A candidate pair is only ever reported as a contradiction
    when both of the following hold:

    1. Mechanical checks: actions differ, predicate fields overlap, and simple
       conjunctions are not provably disjoint equality/numeric ranges. These
       are checked before spending a conflict-verification LLM call. Rules
       from the *same* document are never paired (same-document divergence is
       handled by ``skiljo_core.simulation.contradictions``).
    2. LLM confirmation: a second, focused LLM call is asked whether the
       two rules truly conflict (as opposed to merely covering different
       situations), and must answer yes.

    This two-part gate is the "mechanical conflict verification" the
    detector is required to perform: the LLM proposes and explains, but
    never gets the final word alone.
    """
    if len(policies) < 2:
        return []

    surface_groups: dict[str, list[RuleRef]] = defaultdict(list)
    for policy in policies:
        for ref in _rule_refs(policy):
            surface = _assign_decision_surface(llm_client, ref, model)
            surface_groups[surface].append(ref)

    contradictions: list[CrossDocumentContradiction] = []
    for surface, refs in surface_groups.items():
        for i, ref_a in enumerate(refs):
            for ref_b in refs[i + 1 :]:
                if ref_a.policy_id == ref_b.policy_id:
                    continue
                if ref_a.action == ref_b.action:
                    continue
                if not _conditions_may_overlap(ref_a.condition, ref_b.condition):
                    continue
                check = _check_conflict(llm_client, ref_a, ref_b, surface, model)
                if not check.is_conflict:
                    continue
                contradictions.append(
                    CrossDocumentContradiction(
                        decision_surface=surface,
                        policy_1=ref_a.policy_id,
                        policy_2=ref_b.policy_id,
                        action_1=ref_a.action,
                        action_2=ref_b.action,
                        rationale=check.rationale,
                        citation_1=_citation(ref_a),
                        citation_2=_citation(ref_b),
                    )
                )
    return contradictions
