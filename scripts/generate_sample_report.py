from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from jinja2 import Environment, FileSystemLoader

from skiljo_core.schemas.simulation_report_schema import (
    Citation,
    Contradiction,
    EstimatedFinancialImpact,
    Result,
    RoiEstimates,
    SimulationReport,
    Zone,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / "packages" / "api" / "src" / "skiljo_api" / "templates"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "demo-artifacts" / "sample-diagnostic-report.html"


def build_sample_report() -> SimulationReport:
    return SimulationReport(
        skill_version_id=UUID("00000000-0000-0000-0000-000000000105"),
        total_tickets=12,
        match_rate=0.75,
        escalation_accuracy=1.0,
        contradiction_count=1,
        automation_candidate_count=8,
        roi_estimates=RoiEstimates(
            automation_safe_volume=8,
            manual_review_hours_per_month=2.0,
            estimated_value_usd=900.0,
        ),
        contradictions=[
            Contradiction(
                cluster_key={"amount_band": "100-500", "customer_segment": "vip"},
                written_decision="human_review",
                observed_decision="approve_refund",
                frequency=0.75,
                ticket_count=12,
                affected_ticket_ids=["ticket-001", "ticket-002", "ticket-003"],
                citation=Citation(
                    policy_id="sample-refund-policy",
                    rule_id="rule-vip-review",
                    span_start=0,
                    span_end=42,
                    quoted_text="Refunds over $100 require human review.",
                ),
                estimated_financial_impact=EstimatedFinancialImpact(
                    divergent_ticket_count=9,
                    average_refund_amount=100.0,
                    estimated_impact_usd=900.0,
                ),
            )
        ],
        results=[
            Result(
                ticket_id=UUID("00000000-0000-0000-0000-000000000001"),
                decision="approve_refund",
                zone=Zone.deterministic,
                matched_human_decision=True,
                reasoning="Refund amount is within the auto-approval threshold.",
            )
        ],
    )


def generate_sample_report(output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("report.html")
    html = template.render(
        report=build_sample_report(),
        skill_name="process_refund_request",
        extracted_rule_count=3,
        generated_at=datetime(2026, 8, 15, tzinfo=UTC),
    )
    output_path.write_text(html)


if __name__ == "__main__":
    generate_sample_report()
