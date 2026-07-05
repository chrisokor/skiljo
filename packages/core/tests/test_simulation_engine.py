import asyncio
import uuid

import pytest

from skiljo_core.schemas.rule_schema import (
    Condition,
    ConditionOrPredicate,
    DeterministicRule,
    Operator,
    Predicate,
)
from skiljo_core.schemas.skill_schema import DecisionZones, Input, Skill, Type
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.engine import compute_report, simulate_batch
from skiljo_core.testing import FakeLLMClient


def _simple_skill() -> Skill:
    return Skill(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[Input(name="refund_amount", type=Type.number)],
        decision_zones=DecisionZones(
            deterministic=[
                DeterministicRule(
                    condition=Condition(
                        all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lte, value=100.0))]
                    ),
                    action="approve_refund",
                )
            ],
            llm_assisted=[],
            human_only=[],
        ),
    )


def _tickets(count: int, approved_count: int) -> list[Ticket]:
    tickets = []
    for i in range(count):
        amount = 50.0 if i < approved_count else 200.0
        gt = "approve_refund" if i < approved_count else "escalate_to_human"
        tickets.append(
            Ticket(
                ticket_id=uuid.uuid4(),
                refund_amount=amount,
                purchase_days_ago=10,
                ground_truth_decision=gt,
            )
        )
    return tickets


def test_simulate_batch_returns_one_result_per_ticket() -> None:
    skill = _simple_skill()
    tickets = _tickets(10, 5)
    results = asyncio.run(simulate_batch(skill, tickets, FakeLLMClient([])))
    assert len(results) == 10


def test_simulate_batch_all_deterministic_no_llm_calls() -> None:
    skill = _simple_skill()
    tickets = _tickets(5, 5)
    fake = FakeLLMClient([])
    asyncio.run(simulate_batch(skill, tickets, fake))
    assert len(fake.calls) == 0


def test_compute_report_match_rate() -> None:
    skill_version_id = uuid.uuid4()
    tickets = _tickets(10, 7)
    results = asyncio.run(simulate_batch(_simple_skill(), tickets, FakeLLMClient([])))
    report = compute_report(skill_version_id, results, tickets)
    assert report.match_rate == pytest.approx(1.0)  # all decisions match ground truth


def test_compute_report_automation_candidate_count() -> None:
    skill_version_id = uuid.uuid4()
    tickets = _tickets(10, 4)
    results = asyncio.run(simulate_batch(_simple_skill(), tickets, FakeLLMClient([])))
    report = compute_report(skill_version_id, results, tickets)
    assert report.automation_candidate_count == 4  # 4 hit deterministic zone


def test_compute_report_empty_returns_zero_match_rate() -> None:
    report = compute_report(uuid.uuid4(), [], [])
    assert report.match_rate == 0.0
    assert report.escalation_accuracy == 1.0


def test_compute_report_escalation_accuracy_all_correct() -> None:
    skill_version_id = uuid.uuid4()
    # All escalations should match ground truth (escalate_to_human)
    tickets = _tickets(6, 0)  # all above threshold → all escalate → all match ground truth
    results = asyncio.run(simulate_batch(_simple_skill(), tickets, FakeLLMClient([])))
    report = compute_report(skill_version_id, results, tickets)
    assert report.escalation_accuracy == pytest.approx(1.0)
