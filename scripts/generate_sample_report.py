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
_POLICY_QUOTE = "Refunds over $100 require human review."


def build_sample_report() -> SimulationReport:
    results = [
        Result(
            ticket_id=UUID(f"00000000-0000-0000-0000-{index:012d}"),
            decision="human_review" if index in {7, 8, 10} else "approve_refund",
            zone=(
                Zone.deterministic
                if index <= 8
                else Zone.llm_assisted
                if index <= 10
                else Zone.human_only
            ),
            matched_human_decision=index not in {7, 8, 10},
            reasoning=(
                "Written policy requires review, but historical handling approved the refund."
                if index in {7, 8, 10}
                else "Written policy and historical handling agree."
            ),
        )
        for index in range(1, 13)
    ]
    affected_ticket_ids = [str(results[index - 1].ticket_id) for index in (7, 8, 10)]

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
            estimated_value_usd=800.0,
        ),
        contradictions=[
            Contradiction(
                cluster_key={"amount_band": "100-500", "customer_segment": "vip"},
                written_decision="human_review",
                observed_decision="approve_refund",
                frequency=0.75,
                ticket_count=4,
                affected_ticket_ids=affected_ticket_ids,
                citation=Citation(
                    policy_id="sample-refund-policy",
                    rule_id="rule-vip-review",
                    span_start=0,
                    span_end=len(_POLICY_QUOTE),
                    quoted_text=_POLICY_QUOTE,
                ),
                estimated_financial_impact=EstimatedFinancialImpact(
                    divergent_ticket_count=3,
                    average_refund_amount=150.0,
                    estimated_impact_usd=450.0,
                ),
            )
        ],
        results=results,
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
    html = "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
    output_path.write_text(html)


if __name__ == "__main__":
    generate_sample_report()
