from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from skiljo_core.schemas.simulation_report_schema import Result
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.contradiction_stats import binomial_test_contradiction

_DEFAULT_BASE_ERROR_RATE = 0.05
_DEFAULT_SIGNIFICANCE_MIN_CLUSTER_SIZE = 50


@dataclass
class Citation:
    policy_id: str
    rule_id: str
    span_start: int
    span_end: int
    quoted_text: str


@dataclass
class FinancialImpact:
    divergent_ticket_count: int
    average_refund_amount: float
    estimated_impact_usd: float


@dataclass
class Contradiction:
    cluster_key: dict[str, Any]
    written_decision: str
    observed_decision: str
    frequency: float
    ticket_count: int
    affected_ticket_ids: list[str] = field(default_factory=list)
    citation: Citation | None = None
    estimated_financial_impact: FinancialImpact | None = None
    # Clustering dimensions (A6): reason category and time window. Populated
    # with the specific bucket value when the cluster was resolved at fine
    # (amount_band x segment x reason x time_window) granularity, or with
    # the dominant value among the diverged tickets when the detector fell
    # back to the coarser amount_band x segment cluster for lack of data.
    reason: str | None = None
    time_window: str | None = None
    # Statistical support (A6): binomial test of the divergence rate against
    # a base error rate, so a flagged cluster can be distinguished from
    # ordinary noise rather than judged on a bare frequency threshold alone.
    p_value: float | None = None
    min_cluster_size: int = _DEFAULT_SIGNIFICANCE_MIN_CLUSTER_SIZE
    supported: bool = False


_Item = tuple[Result, Ticket, str, str]  # (result, ticket, reason, time_window)


def _amount_band(amount: float) -> str:
    if amount <= 50:
        return "0-50"
    if amount <= 100:
        return "51-100"
    if amount <= 200:
        return "101-200"
    if amount <= 500:
        return "201-500"
    return "500+"


def _reason_category(refund_reason: str | None) -> str:
    return refund_reason or "unknown"


def _time_window(purchase_days_ago: int) -> str:
    """Bucket a ticket's age into a coarse time window.

    Tickets carry no absolute calendar date (see Ticket schema), so the time
    dimension is derived from ``purchase_days_ago`` the same way the amount
    dimension is derived from ``refund_amount`` via ``_amount_band``. The
    30-day boundary matches the eligibility threshold already used in policy
    rules (see DESIGN_DOCUMENT.md's `purchase_days_ago lte 30` example).
    """
    if purchase_days_ago <= 7:
        return "0-7d"
    if purchase_days_ago <= 30:
        return "8-30d"
    if purchase_days_ago <= 90:
        return "31-90d"
    return "90d+"


def _mode(values: list[str]) -> str | None:
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]


def _build_contradiction(
    items: list[_Item],
    amount_band: str,
    segment: str,
    threshold: float,
    base_error_rate: float,
    significance_min_cluster_size: int,
    reason: str | None = None,
    time_window: str | None = None,
) -> Contradiction | None:
    diverged = [(r, t) for r, t, _, _ in items if r.decision != t.ground_truth_decision]
    if not diverged:
        return None

    # Most common (written, observed) pair among divergent items.
    pair_counts: Counter[tuple[str, str]] = Counter(
        (r.decision, t.ground_truth_decision) for r, t in diverged
    )
    (written, observed) = pair_counts.most_common(1)[0][0]
    representative_items = [
        (result, ticket)
        for result, ticket in diverged
        if result.decision == written and ticket.ground_truth_decision == observed
    ]
    rate = len(representative_items) / len(items)
    if rate <= threshold:
        return None

    # Metrics and evidence describe the selected decision pair only.
    divergent_amounts = [ticket.refund_amount for _, ticket in representative_items]
    avg_amount = (
        sum(divergent_amounts) / len(divergent_amounts) if divergent_amounts else 0.0
    )
    financial_impact = FinancialImpact(
        divergent_ticket_count=len(representative_items),
        average_refund_amount=avg_amount,
        estimated_impact_usd=avg_amount * len(representative_items),
    )

    cluster_key: dict[str, Any] = {"amount_band": amount_band, "customer_segment": segment}
    if reason is not None:
        cluster_key["reason"] = reason
    if time_window is not None:
        cluster_key["time_window"] = time_window

    # Descriptive reason/time_window: the exact bucket when this cluster was
    # resolved at fine granularity, otherwise the dominant value among the
    # diverged tickets in the coarse fallback cluster.
    descriptive_reason = reason if reason is not None else _mode(
        [_reason_category(ticket.refund_reason) for _, ticket in representative_items]
    )
    descriptive_time_window = time_window if time_window is not None else _mode(
        [_time_window(ticket.purchase_days_ago) for _, ticket in representative_items]
    )

    stats = binomial_test_contradiction(
        {
            "cluster_size": len(items),
            "frequency": rate,
            "divergence_count": len(representative_items),
            "base_error_rate": base_error_rate,
            "min_cluster_size": significance_min_cluster_size,
        }
    )

    return Contradiction(
        cluster_key=cluster_key,
        written_decision=written,
        observed_decision=observed,
        frequency=rate,
        ticket_count=len(representative_items),
        affected_ticket_ids=[str(result.ticket_id) for result, _ in representative_items],
        estimated_financial_impact=financial_impact,
        reason=descriptive_reason,
        time_window=descriptive_time_window,
        p_value=stats["p_value"],
        min_cluster_size=significance_min_cluster_size,
        supported=stats["supported"],
    )


def detect_contradictions(
    results: list[Result],
    tickets: list[Ticket],
    threshold: float = 0.05,
    min_cluster_size: int = 3,
    base_error_rate: float = _DEFAULT_BASE_ERROR_RATE,
    significance_min_cluster_size: int = _DEFAULT_SIGNIFICANCE_MIN_CLUSTER_SIZE,
) -> list[Contradiction]:
    """Detect divergences between skill decisions and ground truth.

    Clusters on four dimensions -- amount band, customer segment, reason
    category, and time window -- completing the Section 5.4 detector design.
    Reason and time window are resolved *within* each amount_band x segment
    group: if the finer (reason, time_window) split still has enough tickets
    per bucket (>= ``min_cluster_size``) to be meaningful, contradictions are
    reported at that finer granularity. Otherwise the detector falls back to
    the coarser amount_band x segment cluster, so recall on small batches
    (e.g. a handful of VIP tickets) isn't lost to over-fragmentation -- a
    real risk once two more dimensions are added on top of amount band and
    segment. This keeps the acceptance bar from DESIGN_DOCUMENT.md Section 12
    (>=0.8 recall on planted divergences, <=1 false positive per run) intact
    under the new clustering.

    Each flagged cluster also carries statistical support: a binomial test
    of its divergence rate against ``base_error_rate`` (see
    ``contradiction_stats.binomial_test_contradiction``), replacing the bare
    frequency threshold as the sole signal. ``supported`` requires both a
    significant p-value and a cluster large enough for the test to have real
    power (``significance_min_cluster_size``, independent of the structural
    ``min_cluster_size`` used to decide whether a cluster is worth
    evaluating at all).
    """
    ticket_map = {str(t.ticket_id): t for t in tickets}

    coarse_groups: dict[tuple[str, str], list[_Item]] = defaultdict(list)
    for result in results:
        ticket = ticket_map.get(str(result.ticket_id))
        if ticket is None:
            continue
        coarse_key = (_amount_band(ticket.refund_amount), ticket.customer_segment or "unknown")
        item: _Item = (
            result,
            ticket,
            _reason_category(ticket.refund_reason),
            _time_window(ticket.purchase_days_ago),
        )
        coarse_groups[coarse_key].append(item)

    contradictions: list[Contradiction] = []
    for (amount_band, segment), coarse_items in coarse_groups.items():
        fine_groups: dict[tuple[str, str], list[_Item]] = defaultdict(list)
        for item in coarse_items:
            _, _, reason, time_window = item
            fine_groups[(reason, time_window)].append(item)

        fine_contradictions = []
        for (reason, time_window), fine_items in fine_groups.items():
            if len(fine_items) < min_cluster_size:
                continue
            contradiction = _build_contradiction(
                fine_items,
                amount_band,
                segment,
                threshold,
                base_error_rate,
                significance_min_cluster_size,
                reason=reason,
                time_window=time_window,
            )
            if contradiction is not None:
                fine_contradictions.append(contradiction)

        if fine_contradictions:
            contradictions.extend(fine_contradictions)
            continue

        if len(coarse_items) < min_cluster_size:
            continue
        contradiction = _build_contradiction(
            coarse_items,
            amount_band,
            segment,
            threshold,
            base_error_rate,
            significance_min_cluster_size,
        )
        if contradiction is not None:
            contradictions.append(contradiction)

    return contradictions
