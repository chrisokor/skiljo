from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from skiljo_core.schemas.simulation_report_schema import Result
from skiljo_core.schemas.ticket_schema import Ticket


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


def detect_contradictions(
    results: list[Result],
    tickets: list[Ticket],
    threshold: float = 0.05,
    min_cluster_size: int = 3,
) -> list[Contradiction]:
    ticket_map = {str(t.ticket_id): t for t in tickets}

    # Cluster by (amount_band, customer_segment)
    clusters: dict[tuple[str, str], list[tuple[Result, Ticket]]] = defaultdict(list)
    for result in results:
        ticket = ticket_map.get(str(result.ticket_id))
        if ticket is None:
            continue
        key = (
            _amount_band(ticket.refund_amount),
            ticket.customer_segment or "unknown",
        )
        clusters[key].append((result, ticket))

    contradictions = []
    for (amount_band, segment), items in clusters.items():
        if len(items) < min_cluster_size:
            continue
        diverged = [
            (r, t) for r, t in items if r.decision != t.ground_truth_decision
        ]
        rate = len(diverged) / len(items)
        if rate <= threshold:
            continue

        # Most common (written, observed) pair among divergent items
        pair_counts: Counter[tuple[str, str]] = Counter(
            (r.decision, t.ground_truth_decision) for r, t in diverged
        )
        (written, observed) = pair_counts.most_common(1)[0][0]

        # Compute financial impact from divergent cluster tickets
        divergent_amounts = [t.refund_amount for _, t in diverged]
        avg_amount = (
            sum(divergent_amounts) / len(divergent_amounts) if divergent_amounts else 0.0
        )
        financial_impact = FinancialImpact(
            divergent_ticket_count=len(diverged),
            average_refund_amount=avg_amount,
            estimated_impact_usd=avg_amount * len(diverged),
        )

        contradictions.append(
            Contradiction(
                cluster_key={"amount_band": amount_band, "customer_segment": segment},
                written_decision=written,
                observed_decision=observed,
                frequency=rate,
                ticket_count=len(items),
                affected_ticket_ids=[str(r.ticket_id) for r, _ in diverged],
                estimated_financial_impact=financial_impact,
            )
        )
    return contradictions
