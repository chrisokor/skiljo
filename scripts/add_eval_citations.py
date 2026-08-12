"""Add mechanically valid candidate citations to train/dev eval skill YAML.

The candidate selector intentionally uses only words present in a rule's action
and predicate fields/values. It writes a full policy paragraph so the quote is
always an exact, reviewable source substring. Review the dry-run output before
using ``--write``. This selector does not establish semantic support. Rules
that have been reviewed against their source use exact evidence overrides,
which this helper preserves and validates on every run.
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

_AWS_AUDIT_CREDIT_AND_CLAIM = (
    "Service Credit Tiers:\n"
    "- Less than 99.9% but greater than or equal to 99.0%: 10% credit of monthly charges\n"
    "- Less than 99.0% but greater than or equal to 95.0%: 25% credit of monthly charges\n"
    "- Less than 95.0%: 100% credit of monthly charges\n\n"
    "Claim Requirements:\n"
    "To receive a Service Credit, customers must submit a request through AWS Support within two "
    "billing cycles of the incident. The claim must include \"SLA Credit Request\" in the subject "
    "line, along with the specific billing cycle, affected region, monthly uptime percentage "
    "documentation, and request logs showing error details from the outage period. Claims submitted "
    "after this deadline will not be eligible for Service Credits."
)
_EC2_CREDIT_AND_CLAIM = (
    "Region-Level Credit Tiers:\n"
    "- Less than 99.99% but equal to or greater than 99.0%: 10% credit of monthly charges\n"
    "- Less than 99.0% but equal to or greater than 95.0%: 30% credit of monthly charges\n"
    "- Less than 95.0%: 100% credit of monthly charges\n\n"
    "Instance-Level SLA\n\n"
    "Individual EC2 instances receive an Instance-Level Uptime Percentage of at least 99.5%.\n\n"
    "Instance-Level Credit Tiers:\n"
    "- Less than 99.5% but equal to or greater than 99.0%: 10% credit of monthly charges\n"
    "- Less than 99.0% but equal to or greater than 95.0%: 30% credit of monthly charges\n"
    "- Less than 95.0%: 100% credit of monthly charges\n\n"
    "Automatic Instance Credit\n\n"
    "AWS will not charge you for any Single EC2 Instance that is Unavailable for more than six "
    "consecutive minutes within a clock-hour. This credit is applied automatically without requiring "
    "a claim submission.\n\n"
    "Claim Requirements\n\n"
    "To receive a Service Credit for SLA violations (other than the automatic instance credit), you "
    "must submit a claim by opening a case in the AWS Support Center. Your claim must:\n"
    "- Include \"Amazon Compute SLA Credit Request\" in the subject line\n"
    "- Specify the dates and times of the unavailability incident\n"
    "- Identify the affected AWS region and Availability Zone\n"
    "- List the affected EC2 resource IDs\n\n"
    "Claims must be received by the end of the second billing cycle after which the incident occurred."
)
_GOOGLE_MULTI_ZONE_CREDIT_AND_CLAIM = (
    "Instances in Multiple Zones:\n"
    "- Less than 99.99% but greater than or equal to 99.0%: 10% credit of monthly charges\n"
    "- Less than 99.0% but greater than or equal to 95.0%: 25% credit of monthly charges\n"
    "- Less than 95.0%: 50% credit of monthly charges\n\n"
    "Single Instance:\n"
    "- Less than 99.5% but greater than or equal to 99.0%: 10% credit of monthly charges\n"
    "- Less than 99.0% but greater than or equal to 95.0%: 25% credit of monthly charges\n"
    "- Less than 95.0%: 50% credit of monthly charges\n\n"
    "Service Credit Cap\n\n"
    "In no event will the total service credits issued in any single billing month exceed 50% of the "
    "amounts paid or payable by you for Compute Engine in that month.\n\n"
    "Claim Notification Window\n\n"
    "To receive a Service Credit, you must submit a request within 30 days of the incident. Claims "
    "submitted after 30 days will not be eligible for credit. Requests must be submitted through the "
    "Google Cloud Console support portal and must include the relevant resource IDs, timestamps, and "
    "a description of the incident."
)
_GOOGLE_SINGLE_INSTANCE_CREDIT_AND_CLAIM = (
    "Single Instance:\n"
    "- Less than 99.5% but greater than or equal to 99.0%: 10% credit of monthly charges\n"
    "- Less than 99.0% but greater than or equal to 95.0%: 25% credit of monthly charges\n"
    "- Less than 95.0%: 50% credit of monthly charges\n\n"
    "Service Credit Cap\n\n"
    "In no event will the total service credits issued in any single billing month exceed 50% of the "
    "amounts paid or payable by you for Compute Engine in that month.\n\n"
    "Claim Notification Window\n\n"
    "To receive a Service Credit, you must submit a request within 30 days of the incident. Claims "
    "submitted after 30 days will not be eligible for credit. Requests must be submitted through the "
    "Google Cloud Console support portal and must include the relevant resource IDs, timestamps, and "
    "a description of the incident."
)

# Literal action/predicate overlap cannot rank these paraphrased rules. This
# small review list also protects persisted citations: validation checks that a
# listed rule still uses its exact reviewed source excerpt.
REVIEWED_EVIDENCE_OVERRIDES = {
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
        "22_stripe_subscription_suspension.skill.yaml",
        3,
    ): (
        "Reinstatement: If you bring your account current within the 30-day suspension\n"
        "window, access is restored immediately upon successful payment. No late fee\n"
        "is assessed for the first payment failure in a rolling 12-month period; a 1.5%\n"
        "monthly late fee applies to any subsequent failure in that window."
    ),
    (
        "train",
        "22_stripe_subscription_suspension.skill.yaml",
        4,
    ): (
        "Reinstatement: If you bring your account current within the 30-day suspension\n"
        "window, access is restored immediately upon successful payment. No late fee\n"
        "is assessed for the first payment failure in a rolling 12-month period; a 1.5%\n"
        "monthly late fee applies to any subsequent failure in that window."
    ),
    (
        "train",
        "26_vercel_pro_spend_management.skill.yaml",
        3,
    ): (
        "Spend management: By default, a Spend Management cap of $200/month is\n"
        "applied to on-demand overage charges. Once cumulative overage charges reach\n"
        "the configured cap, further resource usage that would incur additional\n"
        "charges is paused until the next billing cycle unless the account owner\n"
        "raises or removes the cap."
    ),
    (
        "train",
        "28_google_cloud_compute_zone_config.skill.yaml",
        1,
    ): (
        "Instances in Multiple Zones: If your Covered Instances are configured to run\n"
        "in multiple zones in more than one region, and the monthly uptime percentage\n"
        "falls below 99.99% but at or above 99.0%, you receive a 10% credit. Below\n"
        "99.0% but at or above 95.0%, a 25% credit. Below 95.0%, a 50% credit."
    ),
    (
        "train",
        "28_google_cloud_compute_zone_config.skill.yaml",
        2,
    ): (
        "Single Zone or Single Instance: If your Covered Instances are configured to\n"
        "run as a single instance or within a single zone, the monthly uptime\n"
        "percentage must fall below 99.5% but at or above 99.0% for a 10% credit,\n"
        "below 99.0% but at or above 95.0% for a 25% credit, and below 95.0% for a 50%\n"
        "credit."
    ),
    (
        "train",
        "28_google_cloud_compute_zone_config.skill.yaml",
        3,
    ): (
        "Instances in Multiple Zones: If your Covered Instances are configured to run\n"
        "in multiple zones in more than one region, and the monthly uptime percentage\n"
        "falls below 99.99% but at or above 99.0%, you receive a 10% credit. Below\n"
        "99.0% but at or above 95.0%, a 25% credit. Below 95.0%, a 50% credit.\n\n"
        "Single Zone or Single Instance: If your Covered Instances are configured to\n"
        "run as a single instance or within a single zone, the monthly uptime\n"
        "percentage must fall below 99.5% but at or above 99.0% for a 10% credit,\n"
        "below 99.0% but at or above 95.0% for a 25% credit, and below 95.0% for a 50%\n"
        "credit."
    ),
    (
        "train",
        "28_google_cloud_compute_zone_config.skill.yaml",
        4,
    ): (
        "Instances in Multiple Zones: If your Covered Instances are configured to run\n"
        "in multiple zones in more than one region, and the monthly uptime percentage\n"
        "falls below 99.99% but at or above 99.0%, you receive a 10% credit. Below\n"
        "99.0% but at or above 95.0%, a 25% credit. Below 95.0%, a 50% credit.\n\n"
        "Single Zone or Single Instance: If your Covered Instances are configured to\n"
        "run as a single instance or within a single zone, the monthly uptime\n"
        "percentage must fall below 99.5% but at or above 99.0% for a 10% credit,\n"
        "below 99.0% but at or above 95.0% for a 25% credit, and below 95.0% for a 50%\n"
        "credit.\n\n"
        "In no event will total credits for any billing month exceed 50% of the\n"
        "amount payable for that month, regardless of configuration."
    ),
    (
        "train",
        "29_atlassian_cancellation_mechanics.skill.yaml",
        1,
    ): (
        "Free tier: If you cancel a free-tier product, deactivation is immediate upon\n"
        "cancellation \u2014 there is no grace period because no billing cycle applies."
    ),
    **{
        ("train", "03_aws_audit_manager_sla.skill.yaml", index): _AWS_AUDIT_CREDIT_AND_CLAIM
        for index in (1, 2, 3)
    },
    (
        "train",
        "05_openai_service_credit_terms.skill.yaml",
        2,
    ): (
        "Credits are non-transferable. You may not sell, gift, sublicense, assign, or otherwise "
        "transfer credits to any other individual or entity. Any attempted transfer is void."
    ),
    (
        "train",
        "05_openai_service_credit_terms.skill.yaml",
        4,
    ): (
        "All OpenAI API service credits are non-refundable except where required by applicable law. "
        "Once purchased, credits cannot be exchanged for cash or any other form of consideration."
    ),
    (
        "train",
        "06_twilio_tos.skill.yaml",
        3,
    ): (
        "If you fail to pay the Fees and remedy such failure within fifteen (15) days of the date "
        "Twilio provides you with written notice of the same, then Twilio may:\n"
        "(i) assess, and you will pay, a late fee of the lesser of 1.5% per month or the maximum "
        "amount allowable by law; and\n"
        "(ii) suspend the provision of the Services to all of your accounts until the Fees due are "
        "paid in full."
    ),
    (
        "train",
        "08_vercel_pro_excerpt.skill.yaml",
        1,
    ): (
        "The Pro platform fee is $20/month, which includes 1 deploying team seat and the $20/month "
        "usage credit. Additional deploying seats (Owner or Member roles) are $20/month each. Viewer "
        "seats are free."
    ),
    (
        "train",
        "08_vercel_pro_excerpt.skill.yaml",
        3,
    ): (
        "Every Pro plan includes $20 in monthly credit. This credit applies to all managed "
        "infrastructure billable resources after their respective included allocations are "
        "exceeded.\n\nIncluded Infrastructure Usage\n\n"
        "Each month, you have the following included allocations:\n"
        "- 1 TB Fast Data Transfer\n"
        "- 10,000,000 Edge Requests\n\n"
        "Once you exceed these included allocations, Vercel will charge usage against your monthly "
        "credit before switching to on-demand billing."
    ),
    (
        "train",
        "08_vercel_pro_excerpt.skill.yaml",
        4,
    ): (
        "The Pro platform fee is $20/month, which includes 1 deploying team seat and the $20/month "
        "usage credit. Additional deploying seats (Owner or Member roles) are $20/month each. Viewer "
        "seats are free."
    ),
    **{
        ("train", "10_amazon_ec2_sla.skill.yaml", index): _EC2_CREDIT_AND_CLAIM
        for index in (2, 3, 4)
    },
    (
        "train",
        "12_vercel_tos.skill.yaml",
        3,
    ): "All fees are non-refundable, except as expressly stated otherwise in this Agreement.",
    (
        "train",
        "12_vercel_tos.skill.yaml",
        4,
    ): (
        "If Vercel ceases to offer a service that is not a core Vercel-branded service, Vercel may "
        "provide a pro-rated refund for any prepaid fees attributable to the discontinued service "
        "for the period following cessation."
    ),
    (
        "train",
        "13_vercel_pro_full.skill.yaml",
        3,
    ): (
        "Credit and Allocation Cascade Logic:\n"
        "1. Included allocations are consumed first (no charge).\n"
        "2. After included allocations are exhausted, usage is charged against the $20 monthly credit.\n"
        "3. After the monthly credit is exhausted, usage is billed on-demand at per-unit rates."
    ),
    (
        "train",
        "13_vercel_pro_full.skill.yaml",
        4,
    ): (
        "You will receive automatic notifications when your usage has reached 75% of your monthly "
        "credit. Once you exceed the monthly credit, Vercel switches your team to on-demand usage "
        "and you will receive daily and weekly summary emails of your usage."
    ),
    (
        "train",
        "13_vercel_pro_full.skill.yaml",
        6,
    ): (
        "The following features are available as add-ons:\n"
        "- SAML Single Sign-On: $300/month\n"
        "- HIPAA BAA: $350/month\n"
        "- Advanced Deployment Protection: $150/month\n"
        "- Flags Explorer: $250/month\n"
        "- Observability Plus: $1.20 per 1 million events\n"
        "- Preview Deployment Suffix: $100/month\n"
        "- Static IPs: $100/month per project, plus Private Data Transfer\n"
        "- Web Analytics Plus: $10/month\n"
        "- Speed Insights: $10/month per project"
    ),
    **{
        ("train", "14_notion_regional_override.skill.yaml", index): (
            "If you signed up for a paid Notion subscription by mistake, you can contact us in the "
            "app or email to request a refund within the applicable window:\n"
            "- Monthly billing plan: refund request must be submitted within 3 days of the invoice date.\n"
            "- Annual billing plan: refund request must be submitted within 30 days of the invoice date."
        )
        for index in (2, 3)
    },
    (
        "train",
        "14_notion_regional_override.skill.yaml",
        4,
    ): (
        "If you were invoiced for members who were accidentally added to your workspace, we can "
        "refund the prorated charges if you reach out within three days of the charge."
    ),
    (
        "train",
        "15_shopify_refund_excerpt.skill.yaml",
        1,
    ): (
        "Shopify plans are generally non-refundable as stated in Shopify's Terms of Service. Shopify "
        "does not provide refunds for subscription fees paid."
    ),
    (
        "train",
        "15_shopify_refund_excerpt.skill.yaml",
        2,
    ): (
        "If you believe you have been charged in error or have a special situation, then you can "
        "contact Shopify Support to have your case reviewed. Refund requests are reviewed on a "
        "case-by-case basis by Shopify Support.\n\n"
        "Eligibility windows for case-by-case review:\n"
        "- Monthly subscriptions: within 7 days of invoice issue\n"
        "- First invoice after trial: within 30 days of invoice issue\n"
        "- Annual subscriptions: within 30 days of invoice issue\n"
        "- SEPA Direct Debit: within 14 days of invoice issue\n"
        "- Brazil merchants: within 90 days of invoice issue\n\n"
        "Meeting these time windows does not guarantee a refund. Refund requests are reviewed on a "
        "case-by-case basis by Shopify Support."
    ),
    **{
        ("train", "20_google_cloud_compute_sla.skill.yaml", index): (
            _GOOGLE_MULTI_ZONE_CREDIT_AND_CLAIM
        )
        for index in (4, 5, 6)
    },
    **{
        ("train", "20_google_cloud_compute_sla.skill.yaml", index): (
            _GOOGLE_SINGLE_INSTANCE_CREDIT_AND_CLAIM
        )
        for index in (7, 8, 9)
    },
    (
        "train",
        "21_stripe_subscription_plan_change.skill.yaml",
        3,
    ): (
        "Same-price changes (e.g., switching between plans of equal price): the change\n"
        "takes effect immediately with no proration."
    ),
    (
        "train",
        "23_openai_services_agreement_late_fee.skill.yaml",
        3,
    ): (
        "If a customer disputes a portion of an invoice in good faith, the customer\n"
        "must pay the undisputed portion by the due date; the disputed portion is not\n"
        "subject to a late fee while the dispute is pending resolution."
    ),
    (
        "train",
        "30_github_marketplace_billing.skill.yaml",
        2,
    ): (
        "Upgrades to a higher Marketplace plan take effect immediately, and the\n"
        "prorated difference for the remainder of the current cycle is charged at the\n"
        "time of the upgrade."
    ),
    (
        "dev",
        "01_stripe_subscription_tax_and_refund_exceptions.skill.yaml",
        2,
    ): (
        "All Subscription fees are exclusive of applicable taxes, which are added to\n"
        "each invoice based on your billing address. Subscription fees are\n"
        "non-refundable and non-cancelable once paid, except as required by\n"
        "applicable law.\n\n"
        "Notwithstanding the foregoing, if Stripe discontinues a Subscription Plan\n"
        "feature you were actively using and paying for, and no reasonably comparable\n"
        "replacement is offered, you are entitled to a prorated refund of fees paid\n"
        "for that feature for the remainder of the current billing period."
    ),
    **{
        ("dev", "03_amazon_ec2_dual_sla_claim.skill.yaml", index): (
            "To submit a region-level claim, you must include \"SLA Credit Request\" in the\n"
            "subject line, the affected dates and times, and the affected resource IDs,\n"
            "and submit it by the end of the second billing cycle after the incident\n"
            "occurred. Claims that omit required information or miss the deadline are\n"
            "denied."
        )
        for index in (1, 2)
    },
    (
        "dev",
        "06_openai_credit_transfer_prohibition.skill.yaml",
        1,
    ): (
        "Service Credits expire one year from the date of purchase and are\n"
        "non-refundable at all times, including upon expiration."
    ),
    (
        "dev",
        "08_twilio_late_fee_and_suspension.skill.yaml",
        2,
    ): (
        "If an invoice remains unpaid for 45 days past the invoice date, Twilio may\n"
        "suspend the account's ability to send messages or make calls until the\n"
        "outstanding balance, including accrued late fees, is paid in full."
    ),
    (
        "dev",
        "09_vercel_tos_non_vercel_service_ceasing.skill.yaml",
        2,
    ): (
        "This refund right applies only to Non-Vercel Services; it does not extend to\n"
        "core Vercel platform features, which remain governed by the standard\n"
        "all-fees-nonrefundable policy."
    ),
    **{
        ("dev", "10_vercel_pro_allocation_cascade.skill.yaml", index): (
            "Usage beyond the included allocation cascades to the monthly usage credit:\n"
            "overage is first covered by your remaining $20 usage credit at standard\n"
            "per-unit rates. Once the usage credit is exhausted, any further overage is\n"
            "billed directly at the standard per-unit overage rate on your next invoice."
        )
        for index in (2, 3)
    },
    (
        "dev",
        "11_notion_platform_specific_purchase_routing.skill.yaml",
        2,
    ): (
        "Purchases made online at notion.so or via Google Pay on Android should be\n"
        "directed to Notion support at support@notion.so, and are handled under\n"
        "Notion's standard refund windows."
    ),
    **{
        ("dev", "12_shopify_plus_prepaid_fees_nonrefundable.skill.yaml", index): (
            "If your contract is terminated by Shopify for your material breach, all\n"
            "remaining prepaid fees for the unexpired term are forfeited and no refund is\n"
            "due. If your contract is terminated by you for Shopify's uncured material\n"
            "breach, Shopify will refund a prorated portion of prepaid fees for the\n"
            "unexpired term."
        )
        for index in (1, 2)
    },
    (
        "dev",
        "13_square_reserve_withholding_and_recovery.skill.yaml",
        1,
    ): (
        "Separately, if a merchant incurs fees, fines, or penalties imposed by a card\n"
        "network or Square related to chargebacks or excessive refund activity, the\n"
        "merchant authorizes Square to debit the merchant's linked bank account for\n"
        "those amounts (a \"Recovery Authorization\") without further notice."
    ),
    (
        "dev",
        "15_github_copilot_case_by_case_refund.skill.yaml",
        1,
    ): (
        "GitHub's Terms of Service state that there are no refunds or credits for\n"
        "partial months of service, downgrade refunds, or refunds for unused months\n"
        "with an open account, with no exceptions."
    ),
    (
        "dev",
        "15_github_copilot_case_by_case_refund.skill.yaml",
        2,
    ): (
        "Separately, GitHub's published support flow for Copilot subscriptions\n"
        "describes a 30-day refund window for an unused Copilot subscription, handled\n"
        "case-by-case through the support Virtual Agent. Support agents evaluate each\n"
        "request individually against usage data before approving or denying it."
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
        start = _unique_quote_start(override, policy_text)
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


def _unique_quote_start(quote: str, policy_text: str) -> int:
    occurrences = policy_text.count(quote)
    if occurrences == 0:
        raise ValueError(f"Configured citation override was not found: {quote!r}")
    if occurrences != 1:
        raise ValueError(
            "Configured citation override must occur exactly once in the policy text: "
            f"found {occurrences} occurrences of {quote!r}"
        )
    return policy_text.find(quote)


def _reviewed_citation(quote: str, policy_text: str) -> Citation:
    """Build a validated citation from a unique reviewed source excerpt."""
    start = _unique_quote_start(quote, policy_text)
    citation = Citation.model_validate(
        {"span": {"start": start, "end": start + len(quote)}, "quoted_text": quote}
    )
    validate_citation(citation, policy_text)
    return citation


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


def _replace_existing_citations(skill_file: Path, citations: list[Citation]) -> None:
    """Replace generated citation mappings while preserving surrounding YAML."""
    raw_skill = skill_file.read_text()
    pattern = re.compile(
        r"^(?P<indent>\s+)citation:\n"
        r"(?P=indent)  span:\n"
        r"(?P=indent)    start: \d+\n"
        r"(?P=indent)    end: \d+\n"
        r"(?P=indent)  quoted_text: .*?$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(raw_skill))
    if len(matches) != len(citations):
        raise ValueError(
            f"Found {len(matches)} citation mappings but {len(citations)} rules in {skill_file}"
        )

    replacements: list[tuple[int, int, str]] = []
    for match, citation in zip(matches, citations, strict=True):
        indent = match.group("indent")
        replacements.append(
            (
                match.start(),
                match.end(),
                f"{indent}citation:\n"
                f"{indent}  span:\n"
                f"{indent}    start: {citation.span.start}\n"
                f"{indent}    end: {citation.span.end}\n"
                f"{indent}  quoted_text: "
                f"{json.dumps(citation.quoted_text, ensure_ascii=True)}",
            )
        )

    for start, end, replacement in reversed(replacements):
        raw_skill = raw_skill[:start] + replacement + raw_skill[end:]
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
            validated_citations: list[Citation] = []
            changed = False
            for index, existing_citation in enumerate(existing_citations, start=1):
                citation = Citation.model_validate(existing_citation)
                validate_citation(citation, policy_text)
                override = REVIEWED_EVIDENCE_OVERRIDES.get((split, skill_file.name, index))
                if override is not None:
                    reviewed_citation = _reviewed_citation(override, policy_text)
                    if citation != reviewed_citation:
                        if not write:
                            raise ValueError(
                                f"{skill_file.name} rule {index} does not match its reviewed "
                                "evidence override"
                            )
                        citation = reviewed_citation
                        changed = True
                validated_citations.append(citation)
            if changed:
                _replace_existing_citations(skill_file, validated_citations)
                updated += 1
            print(f"{skill_file.name}: validated {len(rules)} existing citations")
            continue

        citations: list[Citation] = []
        for index, rule in enumerate(rules, start=1):
            override = REVIEWED_EVIDENCE_OVERRIDES.get((split, skill_file.name, index))
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
