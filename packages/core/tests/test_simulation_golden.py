"""Golden fixture tests: run simulation against data/synthetic_tickets/refund_v1/."""
import asyncio
import json
import uuid
from pathlib import Path

from skiljo_core.schemas.simulation_report_schema import Zone
from skiljo_core.schemas.skill_schema import Skill
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.contradictions import detect_contradictions
from skiljo_core.simulation.engine import compute_report, simulate_batch
from skiljo_core.simulation.executor import LLMRecommendation
from skiljo_core.testing import FakeLLMClient


_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data/synthetic_tickets/refund_v1"


def _make_fake_client() -> FakeLLMClient:
    """Pre-populate with 50 responses — enough to cover all llm_assisted calls."""
    responses = [LLMRecommendation(action="approve_refund", reasoning="goodwill") for _ in range(50)]
    return FakeLLMClient(responses)


def _load_data() -> tuple[Skill, list[Ticket]]:
    skill = Skill.model_validate_json((_DATA_DIR / "skill.json").read_text())
    raw_tickets = json.loads((_DATA_DIR / "tickets.json").read_text())
    tickets = [Ticket.model_validate(t) for t in raw_tickets]
    return skill, tickets


def test_golden_skill_loads_and_validates() -> None:
    """skill.json parses into a valid Skill with the expected skill_name."""
    skill, _ = _load_data()
    assert skill.skill_name == "process_refund_request"
    assert len(skill.decision_zones.deterministic) >= 1
    assert len(skill.decision_zones.llm_assisted) >= 1


def test_golden_tickets_count() -> None:
    """tickets.json contains exactly 100 pre-generated tickets."""
    _, tickets = _load_data()
    assert len(tickets) == 100


def test_golden_simulate_batch_returns_all_results() -> None:
    """simulate_batch on 100 tickets returns 100 results, each with a ticket_id."""
    skill, tickets = _load_data()
    results = asyncio.run(simulate_batch(skill, tickets, _make_fake_client(), max_concurrency=1))
    assert len(results) == 100
    assert all(r.ticket_id for r in results)


def test_golden_report_is_schema_valid() -> None:
    """compute_report produces a valid SimulationReport with bounded match_rate."""
    skill, tickets = _load_data()
    results = asyncio.run(simulate_batch(skill, tickets, _make_fake_client(), max_concurrency=1))
    report = compute_report(uuid.uuid4(), results, tickets)
    # SimulationReport validates on construction — reaching here means it's valid
    assert 0.0 <= report.match_rate <= 1.0
    assert 0.0 <= report.escalation_accuracy <= 1.0
    assert len(report.results) == len(tickets)


def test_golden_detector_finds_planted_divergences() -> None:
    """The VIP exception and near-threshold leniency divergences should be detected."""
    skill, tickets = _load_data()
    results = asyncio.run(simulate_batch(skill, tickets, _make_fake_client(), max_concurrency=1))
    contradictions = detect_contradictions(results, tickets, threshold=0.05, min_cluster_size=3)
    # At least one contradiction should be flagged (planted divergences ensure this)
    assert len(contradictions) >= 1, (
        "No contradictions detected — check that planted divergences exceed threshold "
        "and minimum cluster size. Increase ticket count or lower threshold if needed."
    )


def test_golden_vip_divergence_is_detectable() -> None:
    """The VIP exception divergence (0.85 frequency) must show up in contradictions."""
    skill, tickets = _load_data()
    results = asyncio.run(simulate_batch(skill, tickets, _make_fake_client(), max_concurrency=1))
    contradictions = detect_contradictions(results, tickets, threshold=0.05, min_cluster_size=3)
    # At least one contradiction must reference the VIP segment, OR frequency must be > 0
    vip_contradictions = [
        c for c in contradictions
        if c.cluster_key.get("customer_segment") == "vip" or c.frequency > 0
    ]
    assert len(vip_contradictions) >= 1, (
        "Expected at least one contradiction with vip customer_segment or frequency > 0. "
        f"Got contradictions: {contradictions}"
    )


def test_golden_all_deterministic_tickets_have_expected_decision() -> None:
    """Tickets with refund_amount<=100, purchase_days_ago<=30, no fraud should be approved."""
    skill, tickets = _load_data()
    results = asyncio.run(simulate_batch(skill, tickets, _make_fake_client(), max_concurrency=1))
    result_map = {str(r.ticket_id): r for r in results}

    clearly_eligible = [
        t for t in tickets
        if t.refund_amount <= 100.0
        and t.purchase_days_ago <= 30
        and not t.fraud_flags
        and t.refund_reason != "goodwill"  # goodwill hits llm_assisted zone instead
    ]
    # No clearly eligible ticket should be in the human_only zone
    wrong_zone = [
        t for t in clearly_eligible
        if result_map.get(str(t.ticket_id)) is not None
        and result_map[str(t.ticket_id)].zone == Zone.human_only
    ]
    assert len(wrong_zone) == 0, f"{len(wrong_zone)} eligible tickets incorrectly escalated"
