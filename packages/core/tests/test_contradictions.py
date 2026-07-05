import uuid

from skiljo_core.schemas.simulation_report_schema import Result, Zone
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.contradictions import Contradiction, detect_contradictions


def _result(ticket: Ticket, decision: str, zone: Zone = Zone.deterministic) -> Result:
    return Result(
        ticket_id=ticket.ticket_id,
        decision=decision,
        zone=zone,
        matched_human_decision=decision == ticket.ground_truth_decision,
    )


def _ticket(
    refund_amount: float,
    customer_segment: str = "standard",
    ground_truth: str = "approve_refund",
) -> Ticket:
    return Ticket(
        ticket_id=uuid.uuid4(),
        refund_amount=refund_amount,
        purchase_days_ago=10,
        customer_segment=customer_segment,
        ground_truth_decision=ground_truth,
    )


def test_no_contradictions_when_all_decisions_match() -> None:
    tickets = [_ticket(50.0, "standard", "approve_refund") for _ in range(10)]
    results = [_result(t, "approve_refund") for t in tickets]
    assert detect_contradictions(results, tickets) == []


def test_detects_contradiction_above_threshold() -> None:
    """VIP cluster: skill says deny, but 100% of VIP ground truth says approve."""
    vip_tickets = [_ticket(150.0, "vip", "approve_refund") for _ in range(5)]
    vip_results = [_result(t, "deny_refund") for t in vip_tickets]  # skill always denies

    # Non-contradicting standard tickets (same amount band, different segment)
    std_tickets = [_ticket(150.0, "standard", "deny_refund") for _ in range(5)]
    std_results = [_result(t, "deny_refund") for t in std_tickets]

    contradictions: list[Contradiction] = detect_contradictions(
        vip_results + std_results, vip_tickets + std_tickets, threshold=0.05, min_cluster_size=3
    )
    assert len(contradictions) >= 1
    vip_c = next((c for c in contradictions if c.cluster_key.get("customer_segment") == "vip"), None)
    assert vip_c is not None
    assert vip_c.written_decision == "deny_refund"
    assert vip_c.observed_decision == "approve_refund"
    assert vip_c.frequency == 1.0
    assert vip_c.ticket_count == 5


def test_no_contradiction_below_min_cluster_size() -> None:
    """Clusters smaller than min_cluster_size are skipped even if divergence rate is high."""
    tickets = [_ticket(150.0, "vip", "approve_refund") for _ in range(2)]
    results = [_result(t, "deny_refund") for t in tickets]
    contradictions = detect_contradictions(results, tickets, threshold=0.05, min_cluster_size=3)
    assert contradictions == []


def test_no_contradiction_below_threshold() -> None:
    """5% divergence rate below the 10% threshold should not flag."""
    tickets = [_ticket(50.0, "standard", "approve_refund") for _ in range(20)]
    results = [_result(t, "approve_refund") for t in tickets]
    # Override one ticket's result to be wrong (5% rate)
    results[0] = _result(tickets[0], "deny_refund")
    contradictions = detect_contradictions(results, tickets, threshold=0.10, min_cluster_size=3)
    assert contradictions == []
