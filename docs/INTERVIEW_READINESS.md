# Interview Readiness

## 60-Second Summary

Skiljo turns refund, credit, and billing policies into versioned executable `Skill` specs, then simulates those specs against historical tickets to find where written policy and real behavior diverge.

## What Is Demonstrable

- Policy upload through FastAPI.
- Four-pass LLM extraction into structured `Skill` specs.
- Immutable `SkillVersion` persistence.
- Historical ticket CSV import and simulation.
- JSON and standalone HTML diagnostic reports.
- Cross-document contradiction detection.
- Schema-first Python/TypeScript type generation.

## Technical Stories

- Auditability: every rule requires character-offset citations.
- Reliability: structured outputs, Pydantic validation, retries, and citation validation.
- Measurement: train/dev eval corpus, regression gate plumbing, and explicit caveats where metrics are not fully meaningful.
- Product judgment: report artifacts are designed for finance/support-ops review, not just developer logs.

## Honest Limitations

- No payment flow.
- No live customer deployment claim.
- Real-provider eval metrics require deliberate opt-in runs and should be reported with exact model/date/context.
- Background jobs use FastAPI `BackgroundTasks`, so jobs are not durable across process restarts.

## Resume Bullets

- Built Skiljo, a Python/TypeScript policy-fidelity system that extracts refund and billing rules into versioned executable specifications using FastAPI, Pydantic, SQLAlchemy, Streamlit, and a generated TypeScript SDK.
- Designed a four-pass LLM extraction pipeline with structured outputs, validation retries, audit logging, and mandatory character-offset citations linking each rule to source text.
- Implemented historical-ticket simulation and contradiction detection with clustering, statistical support, and estimated financial impact reporting.
- Shipped a complete diagnostic workflow: policy upload, Skill extraction, immutable version persistence, ticket import, simulation, and standalone HTML reports.
