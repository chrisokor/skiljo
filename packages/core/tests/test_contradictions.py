import uuid

from skiljo_core.schemas.simulation_report_schema import Result, Zone
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.contradictions import Citation, Contradiction, FinancialImpact, detect_contradictions


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
    purchase_days_ago: int = 10,
    refund_reason: str | None = None,
) -> Ticket:
    return Ticket(
        ticket_id=uuid.uuid4(),
        refund_amount=refund_amount,
        purchase_days_ago=purchase_days_ago,
        customer_segment=customer_segment,
        refund_reason=refund_reason,
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


def test_financial_impact_populated_on_contradiction() -> None:
    """Detected contradiction carries estimated_financial_impact with correct counts and amounts."""
    amount = 120.0
    vip_tickets = [_ticket(amount, "vip", "approve_refund") for _ in range(5)]
    vip_results = [_result(t, "deny_refund") for t in vip_tickets]

    contradictions = detect_contradictions(
        vip_results, vip_tickets, threshold=0.05, min_cluster_size=3
    )
    assert len(contradictions) == 1
    c = contradictions[0]

    assert c.estimated_financial_impact is not None
    fi = c.estimated_financial_impact
    assert fi.divergent_ticket_count == 5
    assert fi.average_refund_amount == amount
    assert fi.estimated_impact_usd == amount * 5


def test_financial_impact_average_amount_is_mean_of_diverged_tickets() -> None:
    """average_refund_amount is the mean of divergent tickets' refund amounts.

    All three amounts must fall in the same amount band so they form one cluster.
    The 101-200 band covers 101-200, so use 110, 150, 190 => avg 150.
    """
    amounts = [110.0, 150.0, 190.0]  # all in "101-200" band
    tickets = [_ticket(a, "vip", "approve_refund") for a in amounts]
    results = [_result(t, "deny_refund") for t in tickets]

    contradictions = detect_contradictions(
        results, tickets, threshold=0.05, min_cluster_size=3
    )
    assert len(contradictions) == 1
    fi = contradictions[0].estimated_financial_impact
    assert fi is not None
    assert fi.average_refund_amount == 150.0
    assert fi.divergent_ticket_count == 3
    assert fi.estimated_impact_usd == 150.0 * 3


def test_citation_defaults_to_none() -> None:
    """citation is None by default (populated by callers with skill_version info)."""
    vip_tickets = [_ticket(150.0, "vip", "approve_refund") for _ in range(5)]
    vip_results = [_result(t, "deny_refund") for t in vip_tickets]

    contradictions = detect_contradictions(
        vip_results, vip_tickets, threshold=0.05, min_cluster_size=3
    )
    assert len(contradictions) == 1
    assert contradictions[0].citation is None


def test_citation_dataclass_fields() -> None:
    """Citation dataclass holds all required span + text fields."""
    c = Citation(
        policy_id="refund_v1",
        rule_id="rule_001",
        span_start=100,
        span_end=200,
        quoted_text="Refunds are approved within 30 days.",
    )
    assert c.policy_id == "refund_v1"
    assert c.rule_id == "rule_001"
    assert c.span_start == 100
    assert c.span_end == 200
    assert c.quoted_text == "Refunds are approved within 30 days."


def test_financial_impact_dataclass_fields() -> None:
    """FinancialImpact dataclass holds all three numeric fields."""
    fi = FinancialImpact(divergent_ticket_count=10, average_refund_amount=75.0, estimated_impact_usd=750.0)
    assert fi.divergent_ticket_count == 10
    assert fi.average_refund_amount == 75.0
    assert fi.estimated_impact_usd == 750.0


# ---------------------------------------------------------------------------
# A6: binomial test module
# ---------------------------------------------------------------------------


def test_binomial_test_detects_significant_divergence() -> None:
    """Binomial test rejects null hypothesis (uniform error rate) for planted divergence."""
    from skiljo_core.simulation.contradiction_stats import binomial_test_contradiction

    # 80 approvals out of 100 when policy says deny = planted VIP exception
    contradiction = {
        "written_decision": "deny",
        "observed_decision": "approve",
        "frequency": 0.80,
        "cluster_size": 100,
        "base_error_rate": 0.05,  # 5% baseline error
    }

    result = binomial_test_contradiction(contradiction)
    assert result["p_value"] < 0.05  # Statistically significant
    assert result["supported"] is True


def test_binomial_test_not_significant_near_base_error_rate() -> None:
    """A divergence rate close to the base error rate should not be flagged as significant."""
    from skiljo_core.simulation.contradiction_stats import binomial_test_contradiction

    contradiction = {
        "frequency": 0.06,
        "cluster_size": 100,
        "base_error_rate": 0.05,
    }
    result = binomial_test_contradiction(contradiction)
    assert result["p_value"] >= 0.05
    assert result["supported"] is False


def test_binomial_test_not_supported_below_min_cluster_size() -> None:
    """Even a significant p-value isn't 'supported' without enough examples for power."""
    from skiljo_core.simulation.contradiction_stats import binomial_test_contradiction

    contradiction = {
        "frequency": 0.80,
        "cluster_size": 10,  # below the default min_cluster_size of 50
        "base_error_rate": 0.05,
    }
    result = binomial_test_contradiction(contradiction)
    assert result["p_value"] < 0.05
    assert result["supported"] is False


def test_binomial_test_uses_explicit_divergence_count_when_given() -> None:
    """An explicit divergence_count takes precedence over deriving it from frequency."""
    from skiljo_core.simulation.contradiction_stats import binomial_test_contradiction

    contradiction = {
        "frequency": 0.9,  # deliberately inconsistent with divergence_count below
        "cluster_size": 10,
        "divergence_count": 1,
        "base_error_rate": 0.05,
    }
    result = binomial_test_contradiction(contradiction)
    assert result["divergence_count"] == 1


# ---------------------------------------------------------------------------
# A6: reason / time_window clustering dimensions
# ---------------------------------------------------------------------------


def test_contradiction_carries_statistical_support_fields() -> None:
    """Every detected contradiction carries p_value/min_cluster_size/supported."""
    vip_tickets = [_ticket(150.0, "vip", "approve_refund") for _ in range(5)]
    vip_results = [_result(t, "deny_refund") for t in vip_tickets]

    contradictions = detect_contradictions(vip_results, vip_tickets, threshold=0.05, min_cluster_size=3)
    assert len(contradictions) == 1
    c = contradictions[0]
    assert c.p_value is not None
    assert c.min_cluster_size == 50
    assert c.supported is False  # cluster of 5 is far below the significance min size


def test_contradiction_reason_and_time_window_resolved_at_fine_granularity() -> None:
    """When every ticket in a cluster shares reason/time_window, those become the cluster key."""
    tickets = [
        _ticket(150.0, "vip", "approve_refund", purchase_days_ago=5, refund_reason="goodwill")
        for _ in range(4)
    ]
    results = [_result(t, "deny_refund") for t in tickets]

    contradictions = detect_contradictions(results, tickets, threshold=0.05, min_cluster_size=3)
    assert len(contradictions) == 1
    c = contradictions[0]
    assert c.reason == "goodwill"
    assert c.time_window == "0-7d"
    assert c.cluster_key["reason"] == "goodwill"
    assert c.cluster_key["time_window"] == "0-7d"


def test_contradiction_falls_back_to_coarse_cluster_when_fine_split_too_small() -> None:
    """A small cluster split across multiple reasons/time windows must not lose recall.

    Three VIP tickets in the same amount band with three different reasons
    and time windows can't support a fine (reason, time_window) split at
    min_cluster_size=3 -- the detector should fall back to the coarser
    amount_band x customer_segment cluster instead of silently dropping it.
    """
    tickets = [
        _ticket(150.0, "vip", "approve_refund", purchase_days_ago=2, refund_reason="goodwill"),
        _ticket(150.0, "vip", "approve_refund", purchase_days_ago=20, refund_reason="product_defect"),
        _ticket(150.0, "vip", "approve_refund", purchase_days_ago=60, refund_reason="changed_mind"),
    ]
    results = [_result(t, "deny_refund") for t in tickets]

    contradictions = detect_contradictions(results, tickets, threshold=0.05, min_cluster_size=3)
    assert len(contradictions) == 1
    c = contradictions[0]
    assert c.cluster_key == {"amount_band": "101-200", "customer_segment": "vip"}
    assert c.ticket_count == 3
    # Descriptive dominant reason/time_window are still populated even though
    # they weren't used as the grouping key for this fallback cluster.
    assert c.reason in {"goodwill", "product_defect", "changed_mind"}
    assert c.time_window in {"0-7d", "8-30d", "31-90d"}
