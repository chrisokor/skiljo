# Business Requirements Document

## Project: Governed Workflow Skills for AI Agents

## 1. Vision

Every company will need a living, structured representation of how it actually works — one that AI agents can execute against.

This product is the layer between messy company artifacts and reliable AI automation. It converts company-specific policies, approvals, exceptions, and operational procedures into executable skills that agents can use safely.

The product is not enterprise search.

The product is not a chatbot over documents.

The product is a governed execution layer for company-specific workflows.

## 2. Executive Summary

AI agents are becoming capable of holding conversations, calling tools, and completing simple tasks. But they fail when work requires company-specific judgment.

The bottleneck is no longer just model capability. The bottleneck is knowing how a specific company operates.

For example:

* When is a refund allowed?
* Who approves a billing exception?
* What customer segments get special handling?
* What must be logged for audit?
* Which systems must be updated?
* When does finance, risk, or compliance need to review?

Today, that knowledge is scattered across policy docs, Slack threads, support tickets, finance rules, internal approvals, and human memory.

The product starts with a narrow wedge: finance-sensitive refund, credit, and billing adjustment workflows at fintech companies.

It ingests policy docs and historical behavior, identifies contradictions and edge cases, asks workflow owners structured questions, compiles an executable skill, simulates it against past tickets, and then helps the company decide which parts of the workflow can eventually be trusted to an AI agent.

The first sellable product is not live automation.

The first sellable product is the historical simulation and policy contradiction report.

## 3. Strategic Positioning

### Core Positioning

Decagon handles the support conversation.
We handle the governed workflow behind it.

Vertical support-agent companies are strong at customer-facing interactions. But many valuable workflows do not end in the conversation. Refunds, credits, chargebacks, contract exceptions, and billing approvals often require finance, risk, compliance, and internal systems to agree.

The wedge is not generic refunds.

The wedge is:

> Refunds, credits, and billing adjustments where mistakes are expensive because they touch finance, approvals, contract exceptions, compliance, or the ledger.

### Long-Term Positioning

Refunds are the wedge, not the company.

The long-term product is the governed skill layer companies use to let AI agents safely execute company-specific work across finance, support, sales ops, HR, and engineering.

Every company-specific workflow with policy, approvals, exceptions, and tool calls can become a skill.

## 4. Target Customer

### Initial ICP

The initial target customer is a B2B SaaS or fintech company with usage-based, consumption, or hybrid billing, with:

* 50–1,000 employees
* Usage-based or hybrid billing creating frequent credit memos, refunds, or billing adjustments
* Manual finance approval for credit/refund exceptions
* Revenue-recognition or audit pressure on adjustments
* Fragmented policy and approval processes across Support, Finance, and RevOps
* Existing support automation that cannot touch billing-impacting workflows

### Why This Sub-Segment

Usage-based billing creates a structural source of adjustment work that flat-rate SaaS does not have:

* Customers dispute metered consumption
* Proration and overage rules are ambiguous
* Contract-specific terms create per-customer exceptions
* Revenue-recognition implications make every adjustment a finance event
* New product or pricing launches change billing logic frequently, causing policy drift

In these companies, the Controller feels the pain weekly, not quarterly. Credit memos and billing adjustments are the highest-judgment, highest-frequency, hardest-to-deflect cases.

This is narrower than "fintech." It excludes neobanks (Reg E largely settles policy), pure consumer fintech (low per-case judgment cost), and payments infrastructure (different buyer profile).

It includes:

* B2B SaaS with usage-based or consumption pricing
* B2B fintech with metered or transaction-fee pricing
* Companies built on Stripe Billing, Metronome, Orb, m3ter, or Lago
* API and developer-platform companies with consumption pricing

### Later Expansion Verticals

* Flat-rate B2B SaaS
* Marketplaces
* Healthcare billing
* Logistics
* BNPL and subscription companies with chargebacks or contract exceptions

### Avoid Initially

Pure consumer support teams, flat-rate SaaS with low credit volume, and regulated banking where statutory rules largely preempt the policy-fidelity problem.

## 5. Buyer

### Primary Buyer

The initial buyer is the **Controller / Head of Finance Operations at B2B SaaS or fintech companies with usage-based billing**.

This is the person who owns the pain when refund, credit, or billing adjustment workflows create reconciliation errors, audit risk, inconsistent approvals, or manual finance review.

Support Ops feels the ticket-volume pain, but Finance owns the risk.

The first sales motion should therefore be Finance-led, not Support-led.

### Why This Buyer

The Controller or Head of Finance Ops already cares about:

* Refund approval thresholds
* Credit memo consistency
* Ledger reconciliation
* Audit trails
* Policy exceptions
* Chargeback exposure
* Manual review cost
* Credit memo backlog from metered billing disputes
* Revenue-recognition impact of adjustments
* Quarterly close pressure from unreconciled credits
* Approval controls

They are also more likely than Support Ops to care about the differentiated part of the product: policy fidelity, simulation, contradiction detection, and governed execution.

### Secondary Stakeholders

Support Ops is a key user and stakeholder, but not the first check-writer.

Support Ops cares about:

* Lower handle time
* Fewer escalations
* Faster customer resolution
* Cleaner handoff to Finance

Risk and Compliance are approval stakeholders.

They care about:

* Fraud patterns
* Regulated workflows
* Auditability
* Policy drift
* Exception controls

### Buyer-Specific Positioning

For the Controller:

> We show where your refund and credit policies disagree with actual behavior, then help you turn the approved policy into an executable workflow agents can safely use.

For Support Ops:

> We reduce the number of refund and credit cases your team has to escalate manually.

For Risk/Compliance:

> We make sure agent-executed workflows have approval gates, audit logs, and versioned policy controls.

## 6. Problem Statement

AI support agents can answer customer questions, but they often cannot safely execute workflows that involve money, approvals, or policy exceptions.

A support bot may answer:

> "Where is my refund?"

But it usually cannot safely decide:

* Whether to issue a $700 refund
* Whether an enterprise customer has a contract exception
* Whether finance approval is required
* Whether the customer has chargeback history
* Whether the refund creates reconciliation work
* Whether the case must be escalated
* Which audit trail must be created

Companies therefore keep humans in repetitive workflows, even when much of the work is automatable.

## 7. Core Product Primitive

The core primitive is not a document, vector, or chatbot answer.

The core primitive is a **Company Skill**.

A Company Skill is a structured, versioned, permission-aware workflow that an AI agent can execute.

Example:

```yaml
skill_name: process_refund_request
owner: finance_ops
co_owners:
  - support_ops
  - risk_ops
version: 1.3
trigger:
  - customer_requests_refund
inputs:
  - customer_id
  - order_id
  - refund_reason
  - refund_amount
decision_zones:
  deterministic:
    - if purchase_days_ago <= 30 and refund_amount <= 100 and no_fraud_flags:
        action: approve_refund
  llm_assisted:
    - if goodwill_exception_requested:
        action: draft_recommendation
        requires_human_approval: true
  human_only:
    - if refund_amount > 500:
        action: escalate_to_finance
tools:
  - billing.read_customer
  - zendesk.update_ticket
  - stripe.refund
  - slack.notify_channel
audit_requirements:
  - log_reason
  - store_policy_reference
  - attach_customer_message
permissions:
  data_access:
    - zendesk.ticket.read
    - stripe.customer.read
  allowed_actions:
    - zendesk.ticket.update
    - slack.message.send
  restricted_actions:
    - stripe.refund.execute
approval_required:
  - stripe.refund.execute if refund_amount > 100
```

## 8. Execution Philosophy

The product uses a hybrid execution model.

### Zone 1: Deterministic Execution

Used when company policy is clear.

Example:

```text
Refund under $100, within 30 days, no fraud flags, non-enterprise customer.
```

The agent can eventually execute automatically.

### Zone 2: LLM-Assisted Judgment

Used when context must be interpreted.

Example:

```text
Customer asks for a goodwill exception after poor service experience.
```

The LLM can summarize context, recommend a decision, and draft a response, but cannot complete the side-effecting action without approval.

### Zone 3: Human-Only Execution

Used for high-risk workflows.

Examples:

* Refunds above threshold
* Fraud or abuse flags
* Enterprise contract exceptions
* Legal threats
* Compliance-sensitive cases
* Chargebacks
* Customer success exceptions

The agent prepares the case and routes it to the correct human.

## 9. Process Extraction Strategy

The hardest part of the product is extracting reliable workflow logic.

The extraction strategy has four layers.

### Layer 1: Explicit Policy Ground Truth

Start with policy docs, not Slack magic.

Sources:

* Refund policies
* Credit policies
* Support playbooks
* Help center articles
* Finance rules
* Approval matrices
* Internal macros
* Notion or Confluence docs

The system extracts:

* Eligibility rules
* Thresholds
* Required approvals
* Prohibited actions
* Escalation conditions
* Required customer language
* Audit requirements

### Layer 2: Behavioral Exception Mining

Then compare explicit policy against historical behavior.

Sources:

* Support tickets
* Slack approvals
* Refund history
* Credit memo history
* CRM notes
* Finance approvals
* Manager overrides

The system identifies:

* Repeated exceptions
* Approval patterns
* Informal rules
* Policy overrides
* Common escalation paths
* Contradictions between written policy and actual behavior

### Layer 3: Structured Human Clarification

The workflow owner resolves ambiguity through structured Q&A.

Example:

```text
We found 42 cases where refunds over $500 were escalated to Finance.

Should this become a formal rule?

A. Yes, require Finance approval above $500.
B. No, this was temporary.
C. Use a different threshold.
D. Only apply this to enterprise customers.
```

The product does not hallucinate company policy. It drafts candidate logic and asks humans to approve ambiguous rules.

### Layer 4: Runtime Feedback

Every execution eventually creates feedback:

* Human override
* Escalation
* Approval
* Reopened ticket
* Failed tool call
* Customer complaint
* Chargeback
* Policy exception

Feedback creates proposed amendments, not silent policy changes.

For the MVP, this layer is represented in the skill design but is not fully automated.

## 10. Policy vs. Practice Contradiction Detection

Company docs are often wrong or outdated.

The product surfaces contradictions as a deliverable.

Example:

```text
Written policy: Annual plans are non-refundable.
Actual behavior: 14 annual-plan customers received partial credits in the last quarter.
```

The contradiction report includes:

* Written policy
* Actual historical behavior
* Frequency of deviation
* Customer segment affected
* Financial impact
* Risk level
* Recommended resolution

This creates value before live automation. It helps finance, support, and risk align on what the policy actually is.

## 11. Historical Simulation Report

The simulation report is the central trust artifact.

Before any agent goes live, the product replays the proposed skill against historical tickets.

Example:

```text
We replayed your last 2,000 refund tickets through the proposed refund skill.

1,847 matched historical human decisions.
96 would have escalated correctly.
57 revealed policy/practice contradictions.
0 high-risk cases would have been auto-approved.
214 low-risk cases could have been automated.
Estimated time savings: 36 support hours/month.
Estimated finance review reduction: 18%.
```

### Why It Matters

The simulation report gives the buyer proof before deployment.

It shows:

* Policy fidelity
* Risk boundaries
* Automation potential
* Contradictions
* Escalation accuracy
* Estimated savings

This is the sales artifact that converts interest into paid pilots.

## 12. Runtime Feedback and Amendment Workflow

Runtime feedback should not silently rewrite live skills.

Instead, it creates proposed amendments.

### Feedback Sources

* Human overrides
* Escalations
* Reopened tickets
* Chargebacks
* Failed tool calls
* Customer complaints
* Manager approvals
* Finance corrections
* Compliance flags

### Amendment Flow

1. Capture feedback.
2. Detect pattern.
3. Propose amendment.
4. Send weekly digest to workflow owner.
5. Require approval for material changes.
6. Create new skill version.
7. Log every version change.

### Cross-Functional Ownership

Refund skills may span support, finance, and risk.

Therefore, amendments can require joint ownership:

* Finance owns refund thresholds and reconciliation rules.
* Support owns customer communication logic.
* Risk owns fraud/abuse logic.
* Compliance owns regulated policy constraints.

Finance or Risk has veto rights on rules that affect ledger, approval thresholds, or compliance.

### Auto-Merge Policy

Low-risk changes may auto-merge in later versions:

* Internal note formatting
* Customer response template wording
* Extra logging fields
* Non-side-effecting classification improvements

High-risk changes never auto-merge:

* Refund thresholds
* Approval rules
* Finance logic
* Fraud/risk rules
* Compliance logic
* Tool permissions
* Enterprise exceptions

## 13. Functional Requirements

### FR-1: Workflow-Specific Ingestion

The system shall ingest workflow-specific artifacts.

MVP sources:

* Policy docs
* Support tickets
* Approval notes
* Slack approval examples if available
* CSV exports from billing/refund systems

The MVP does not require deep real-time integrations. Uploads and exports are acceptable for first pilots.

### FR-2: Policy Rule Extraction

The system shall extract candidate rules from explicit documentation.

Rules include:

* Eligibility
* Thresholds
* Approvals
* Escalations
* Required fields
* Required logs
* Prohibited actions

### FR-3: Exception Mining

The system shall identify behavioral patterns that differ from written policy.

### FR-4: Structured Owner Q&A

The system shall ask targeted questions where evidence is missing, contradictory, or risky.

### FR-5: Skill Compilation

The system shall compile approved workflow logic into an executable skill specification.

Each skill includes:

* Owner
* Co-owners
* Version
* Trigger
* Inputs
* Decision zones
* Approval gates
* Audit requirements
* Source evidence
* Future execution permissions

### FR-6: Historical Simulation

The system shall replay skills against historical cases and produce a simulation report.

### FR-7: Human Review

The system shall allow workflow owners to approve, reject, or edit extracted skills before production use.

### FR-8: Exportable Skill Spec

The system shall export an approved workflow skill in a structured format.

V1 should focus on one primary interface:

* JSON/YAML skill specification

V1.1+ may expose:

* MCP server endpoints
* OpenAPI tool definitions
* Anthropic-compatible Skills
* Adapters for OpenAI, Google, and future agent platforms

The first version should not hedge across every possible agent standard.

### FR-9: Permission Design

The MVP shall design skills around per-skill delegated authority, even if runtime enforcement is deferred.

Each skill defines:

* Data access required
* Actions allowed
* Actions restricted
* Approval requirements
* Future tool-call limits

### FR-10: Audit Design

The MVP shall define what a future audit log must capture.

Audit fields include:

* Skill used
* Skill version
* Inputs
* Rules applied
* Sources referenced
* Tool calls made
* Human approvals requested
* Final action
* Errors or escalations

Full runtime audit infrastructure is v1.1+.

## 14. Permissions Model

The recommended model is **per-skill delegated authority**.

Each skill has its own scope:

```yaml
permissions:
  data_access:
    - zendesk.ticket.read
    - stripe.customer.read
  allowed_actions:
    - zendesk.ticket.update
    - slack.message.send
  restricted_actions:
    - stripe.refund.execute
  approval_required:
    - stripe.refund.execute if refund_amount > 100
```

### Why Not Pure Service Accounts?

Service accounts are simple but can over-permission agents.

### Why Not Pure User Permissions?

User-inherited permissions match existing access control, but autonomous workflows may fail if the triggering user lacks access.

### Recommended Approach

Use service accounts underneath during early pilots if needed, but expose per-skill delegated authority as the product abstraction.

That is what enterprise buyers can audit and approve.

## 15. MVP Scope

### MVP Goal

The MVP should prove that a company's refund and credit policy can be extracted, compared against historical behavior, and turned into an approved executable skill.

The first sellable product is **not** live automation.

The first sellable product is the **historical simulation and policy contradiction report**.

Live runtime comes only after the buyer trusts the extracted workflow.

### MVP Customer

A B2B SaaS or fintech company with usage-based billing where the Controller or Head of Finance Ops owns refund, credit, or billing exception risk.

### MVP Workflow

Finance-sensitive refunds, credits, billing adjustments, or customer account credits.

### MVP Features

The MVP has only four required features.

#### 1. Policy + Ticket Ingestion

Ingest workflow-specific data:

* Refund or credit policy docs
* Support tickets
* Approval notes
* Slack approval examples if available
* CSV export or sample data from billing/refund systems

This does not need deep integrations at first. File upload and exports are acceptable for the first pilots.

#### 2. Skill Compiler

Extract the proposed workflow into a structured skill.

The skill should include:

* Eligibility rules
* Approval thresholds
* Required finance review
* Escalation conditions
* Exception categories
* Required audit fields
* Deterministic, LLM-assisted, and human-only zones

#### 3. Historical Simulation Report

Replay the proposed skill against past cases.

The report shows:

* Where the skill matches historical human decisions
* Where it would have escalated
* Where written policy contradicts actual behavior
* Which cases are safe candidates for automation
* Which cases require finance/risk review
* Estimated time saved
* Estimated manual review reduction

This is the core MVP artifact.

#### 4. Human Review UI

Allow the Controller or workflow owner to:

* Review extracted rules
* See evidence behind each rule
* Approve or reject proposed thresholds
* Mark cases as human-only
* Resolve contradictions
* Export an approved workflow spec

### Explicitly Out of Scope for MVP

The MVP should not include:

* Full governed runtime
* Production agent execution
* MCP server deployment
* Multi-agent support
* Deep bidirectional integrations
* Full audit-log infrastructure
* Workflow marketplace
* Broad company ontology
* Multi-vendor agent adapters

These are v1.1+ after the simulation report proves buyer demand.

### MVP Success Metric

The MVP succeeds if a Controller says:

> This report found real policy gaps, matched our past decisions well enough to trust, and identified a narrow class of cases we would let an agent handle next.

### MVP Commercial Goal

Convert simulation report buyers into recurring policy-fidelity customers, then graduate them into governed runtime customers.

The sequence is:

```text
Paid diagnostic → continuous policy fidelity → narrow runtime pilot → expanded automation boundary
```

The recurring tier is the second sellable product, not just a stepping stone to runtime. It earns its own monthly contract on policy drift, expanding scope, and audit evidence — independent of whether the customer ever turns on live execution.

## 16. Deployment Timeline

### Time-to-First-Value After Data Access

Target:

```text
1 week
```

Deliverables:

* Draft skill
* Simulation report
* Policy/practice contradiction report
* Automation opportunity estimate

### Time From Signed Pilot to Live Agent

Realistic:

```text
4–6 weeks for a narrow runtime pilot
```

Reasons:

* Security review
* Integration approvals
* Data access
* Sandbox setup
* Workflow owner availability
* Finance/risk review
* Production approval

## 17. Services-to-Software Transition

The first 10 customers will be white-glove.

That is acceptable as long as every engagement productizes repeatable pieces.

### Customers 1–3

Manual founder-led workflow mapping.

Goal:

* Learn patterns
* Build first schemas
* Build first simulation reports
* Identify buyer language

### Customers 4–10

Semi-automated workflow extraction.

Goal:

* Reuse onboarding questionnaire
* Reuse policy parser
* Reuse simulation engine
* Reuse skill templates

### Customers 10–25

Repeatable deployment.

Goal:

* Customer uploads docs
* System proposes skill
* Workflow owner answers structured Q&A
* Simulation report generated automatically
* Human approves skill

### Customers 25+

Software-led onboarding.

Goal:

* Lower founder involvement
* Repeatable deployment playbook
* Gross margin moves toward SaaS-like levels

### Gross Margin Transition

```text
Customers 1–10: 20–40% gross margin
Customers 10–25: 40–60% gross margin
Customers 25+: 70%+ gross margin
```

## 18. Pricing

Pricing has three tiers tied to a value progression: diagnostic, continuous policy fidelity, governed runtime.

### Tier 1: Paid Diagnostic

The first sellable product is the historical simulation and contradiction report.

```text
$10,000–$25,000 one-time paid diagnostic
```

Deliverables:

* Policy extraction from existing docs
* Historical simulation against past cases
* Policy/practice contradiction report
* Approved workflow skill spec
* Runtime pilot recommendation

Sized to fit a Controller's discretionary budget. Sub-$25K typically does not require procurement at the target ICP.

### Tier 2: Continuous Policy Fidelity (Recurring)

The diagnostic is a snapshot. Policy and practice drift continuously, especially at companies with usage-based billing where pricing and product changes are frequent.

The recurring product solves three problems the diagnostic cannot:

**1. Policy Drift Detection**

Every pricing change, product launch, or contract negotiation creates new edge cases. Quarterly re-simulation catches new contradictions before they surface in audit or close.

**2. Expanding Skill Coverage**

Most customers start with one workflow (refunds) and quickly discover three more (credits, billing adjustments, enterprise exceptions) that want the same treatment. The recurring fee covers continuous extraction of new skills as scope expands.

**3. Audit-Ready Evidence**

Quarterly contradiction reports and versioned skill specs become the artifact the Controller hands to auditors when asked "why was this credit approved?" — converting an ad-hoc forensic exercise into a standing system of record.

Recommended pricing:

```text
$3,000–$8,000/month
```

Scoped by number of active workflow skills and case volume simulated.

### Tier 3: Governed Runtime (V1.1+)

Once the customer trusts the extracted skill, they upgrade to live execution.

```text
Base platform fee + per-executed workflow
```

or:

```text
Percentage of verified manual review reduction
```

The recurring tier de-risks the runtime upsell. Customers are not signing up for AI execution on day one. They sign up for policy fidelity, then graduate to runtime once the simulation report has earned trust.

### Why This Structure Works

* **The diagnostic gets in the door.** A one-time spend on a clear deliverable is approvable without procurement.
* **The recurring fee has a continuity-of-value story.** Policy drift, expanding scope, and audit evidence each independently justify the monthly cost — even before runtime exists.
* **The runtime is a natural upsell, not a cold sell.** It is sold to a customer who already trusts the underlying skill.

This sequencing also drives the services-to-software transition: early customers pay for diagnostics, later customers add recurring fidelity, mature customers are on runtime contracts.

## 19. Competitive Landscape

### Vertical AI Support Agents

Competitors:

* Decagon
* Sierra
* Maven AGI
* Crescendo
* Intercom
* Zendesk AI

They are strong at:

* Customer-facing chat
* Support deflection
* Knowledge-base answers
* Simple actions
* Escalation

Skiljo differs because it focuses on governed workflows that cross support, finance, risk, compliance, and internal systems.

### Why Decagon and Sierra Do Not Automatically Win This

Vertical support-agent companies have strong distribution and own the customer conversation. They are optimized around metrics like ticket deflection, response quality, containment, and customer satisfaction.

That is not the same product surface as finance-governed workflow execution.

A support agent can answer a refund question. But finance-sensitive refunds require a different system of record and a different trust model:

* Written policy must be compared against actual behavior.
* Approval thresholds must be explicit.
* Finance and Risk need veto rights.
* Historical decisions must be replayed before go-live.
* Every action must map to an approved skill version.
* Policy drift must create proposed amendments, not silent behavior changes.
* Ledger-impacting actions need reconciliation logic and auditability.

Decagon and Sierra could build some of this, but it pulls them away from their core product motion: customer conversation automation.

Our wedge is the workflow layer they do not naturally own.

### Competitive One-Liner

Support-agent companies optimize for deflection.

We optimize for policy fidelity.

### Enterprise Search / Knowledge Tools

Competitors:

* Glean
* Guru
* Notion AI
* Dust

They help retrieve and synthesize internal knowledge.

Skiljo turns operational knowledge into executable skills.

### Workflow Automation Tools

Competitors:

* Workato
* Zapier
* Tines
* n8n

They automate deterministic workflows.

Skiljo differs by extracting company-specific decision logic from policy, behavior, and human clarification, then exposing that logic to AI agents with simulation, approvals, and audit logs.

## 20. Defensibility

The defensibility compounds through:

* Historical simulation datasets
* Customer-specific policy graphs
* Approved workflow skills
* Policy-vs-practice contradiction history
* Cross-functional approval logic
* Runtime feedback and amendments
* Finance/risk trust

The more workflows a company approves through the system, the harder it becomes to replace because the product becomes the governed memory of how finance-sensitive work is allowed to happen.

Each quarterly re-simulation deepens the customer-specific policy graph. Every approved amendment, every resolved contradiction, every new skill becomes additional embedded value. By the time a customer is ready for runtime, replacing the system means losing not just the runtime integration but the entire history of approved policy decisions — which Finance and Audit treat as a system of record.

## 21. Technical Architecture

### MVP Architecture

```text
Policy Docs + Ticket Exports
    ↓
Policy Rule Extraction
    ↓
Historical Behavior Analysis
    ↓
Structured Workflow Owner Q&A
    ↓
Skill Compiler
    ↓
Historical Simulation Report
    ↓
Human Review UI
    ↓
Approved Workflow Spec
```

### V1.1+ Architecture

```text
Approved Workflow Spec
    ↓
Governed Agent Runtime
    ↓
Per-Skill Permission Enforcement
    ↓
Tool Execution
    ↓
Audit Log
    ↓
Feedback + Proposed Amendments
```

### MVP Components

1. Ingestion layer
2. Policy parser
3. Exception mining engine
4. Workflow owner Q&A system
5. Skill compiler
6. Simulation engine
7. Human review UI
8. Exportable workflow spec

### Deferred Components

1. Governed runtime
2. MCP server
3. Production tool execution
4. Permission enforcement engine
5. Full audit infrastructure
6. Feedback/amendment automation
7. Multi-agent support

## 22. Success Metrics

### MVP Metrics

* Historical decision match rate on low-risk tickets
* Escalation accuracy
* Number of policy/practice contradictions found
* Number of rules approved by Finance
* Number of safe automation candidates identified
* Diagnostic-to-design-partner conversion rate
* Time-to-report after data access

### Early Targets

```text
70%+ recommendation agreement on low-risk historical cases
50+ historical cases reviewed per diagnostic
5+ material policy/practice contradictions found per pilot
1 week to first simulation report after data access
3–5 design partners from first 50 buyer conversations
```

### Runtime Metrics for V1.1+

* Human override rate
* Time saved per eligible ticket
* Autonomous execution rate within narrow eligible slice
* Number of high-risk cases incorrectly auto-approved
* Manual finance review reduction
* Pilot-to-production conversion rate

## 23. Go-To-Market

### Initial Motion

Founder-led outbound to finance leaders at B2B SaaS and fintech companies with usage-based billing.

Target titles:

* Controller
* Head of Finance Operations
* VP Finance
* Head of Risk Operations
* Revenue Operations leader responsible for billing adjustments

Secondary stakeholders:

* Head of Support Ops
* VP Customer Experience
* Compliance lead

### Lead Magnet

Paid or free historical simulation report.

Pitch:

```text
Give us your refund/credit policy and a sample of past cases. We will show where your team's actual behavior matches policy, where it contradicts policy, and which cases could eventually be automated safely.
```

### 30-Day Goal

Reach 50 target buyers.

Convert 3–5 into design partners.

Use customer language to refine:

* Workflow boundary
* Buyer persona
* Pricing
* Simulation report format
* First runtime pilot

### Discovery Questions

Ask buyers:

```text
When a customer requests a refund, credit, or billing adjustment, which cases still require manual finance approval because support automation cannot be trusted?
```

```text
What refund or credit cases create reconciliation problems?
```

```text
Where does written policy differ from how your team actually handles exceptions?
```

```text
What threshold requires Finance, Risk, or Compliance approval?
```

```text
What evidence would you need before letting an agent handle any part of this workflow?
```

## 24. Risks and Mitigations

### Risk 1: Extracted Workflow Is Wrong

Mitigation:

* Start from explicit policy docs
* Use behavior as candidate exceptions
* Require human approval
* Simulate against historical tickets
* Launch only on low-risk slice later

### Risk 2: Looks Like a Services Business

Mitigation:

* Use white-glove implementation to build repeatable templates
* Productize Q&A, simulation, and skill compilation
* Track gross-margin transition

### Risk 3: Generic Support Agents Expand Into This

Mitigation:

* Focus on finance/risk/compliance-heavy workflows
* Build cross-functional approval logic
* Own simulation and auditability
* Become the governed workflow layer behind support agents

### Risk 4: Policy Drift

Mitigation:

* Feedback creates proposed amendments
* Material changes require owner approval
* Cross-functional rules require cross-functional signoff
* Version every skill

### Risk 5: Enterprise Security Concerns

Mitigation:

* Start with diagnostic reports and exports before production runtime
* Use customer-provided exports when needed
* Design around per-skill delegated authority
* Add runtime permissioning only after buyer demand is proven

### Risk 6: Buyer Pain Is Not Strong Enough

Mitigation:

* Do 10–20 buyer interviews before PRFAQ
* Validate willingness to pay for the simulation report
* Prioritize customers with audit/reconciliation pain
* Avoid low-risk consumer support workflows

## 25. Customer Evidence Needed Before PRFAQ

Before writing the PRFAQ, the team should talk to at least 10 target buyers.

Target buyers:

* Controllers at B2B SaaS or fintech companies with usage-based billing
* Heads of Finance Ops
* VP Finance
* Heads of Risk Ops
* Finance leaders responsible for refunds, credits, billing adjustments, or reconciliation

The goal is to capture direct quotes like:

```text
Anything over $500 goes to Finance.
```

```text
Our support bot can answer the customer, but it cannot issue credits because reconciliation breaks.
```

```text
The policy says one thing, but our team handles VIP customers differently.
```

```text
Audit asks why exceptions were approved, and we do not have a clean trail.
```

```text
Enterprise contract credits are always manual.
```

These quotes should shape the PRFAQ.

The PRFAQ should be written as if a specific real customer is reading it.

## 26. Final Positioning

This product does not compete to be the best support chatbot.

It starts where support chat stops: workflows that touch finance, approvals, compliance, contracts, risk, and internal systems.

The first product is a simulation and contradiction report for finance-sensitive refund, credit, and billing adjustment workflows.

The long-term company is the governed execution layer that turns company-specific operating knowledge into safe, auditable skills for AI agents.

Credit and refund workflows in usage-based billing are the wedge.
The Controller is the first buyer.
The diagnostic earns the first dollar.
Continuous policy fidelity earns the recurring contract.
The skill compiler is the product.
The governed runtime becomes the platform.