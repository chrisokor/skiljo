# PRFAQ: Skiljo

## Project: Governed Workflow Skills for AI Agents

> **Note on placeholders:** The company name is Skiljo (skiljo.ai). Customer quotes and customer company names below are illustrative — they should be replaced with real quotes from the 10–20 buyer interviews described in BRD Section 25 before this PRFAQ is used externally. The press release is mock-future-dated to Q1 2027 to set the launch frame.

---

## Press Release (Mock — Q1 2027)

### Skiljo launches the governed workflow layer for AI agents, starting with finance-sensitive refunds and credits

**Subhead:** Controllers at B2B SaaS and fintech companies with usage-based billing now have a system of record for how policy, practice, and AI execution stay in sync.

**San Francisco, CA — March 4, 2027** — Skiljo today launched the first governed execution layer for AI agents, beginning with refund, credit, and billing adjustment workflows at B2B SaaS and fintech companies with usage-based billing. The product compiles company-specific policy and historical behavior into versioned, auditable skills that AI agents can run safely, with approval gates and full audit logs.

AI support agents can answer customer questions, but they fail when work requires company-specific judgment: whether a refund is allowed, who must approve it, whether the customer has a contract exception, and what must be logged for audit. Skiljo solves the part of the problem that comes after the conversation.

The product launches with three tiers. Customers begin with a paid diagnostic that replays proposed workflow skills against the company's last several thousand historical tickets, surfacing where written policy contradicts actual behavior. Customers then subscribe to continuous policy fidelity, which catches drift after every pricing change, product launch, and contract negotiation. Finally, the governed runtime executes the approved skill autonomously within a Finance-approved boundary.

"Before Skiljo, our team handled credit memos case by case, and Finance had no way to tell whether we were enforcing the policy we wrote down. The contradiction report showed us we were issuing credits in seven scenarios our policy doesn't explicitly allow. We rewrote the policy to match what was actually working, and the runtime now handles the cases we agreed were safe." — *[Placeholder: Controller, mid-market usage-based SaaS company]*

The product is currently available to B2B SaaS and fintech companies with usage-based billing on Stripe Billing, Metronome, Orb, m3ter, or Lago. Pricing starts at $10,000 for the diagnostic and $3,000/month for continuous policy fidelity.

"The companies we work with don't need a better chatbot — they need a governed system for how money-touching workflows are allowed to run. We give Finance the same control they have over a closing checklist, but for AI agents." — *[Placeholder: Founder quote]*

To request a diagnostic, visit skiljo.ai.

---

## External FAQ

### What does Skiljo do?

Skiljo extracts your refund, credit, and billing adjustment policies from existing documentation, compares them against how your team actually handles cases, and turns the result into an executable skill spec. We then replay the proposed skill against your historical tickets and produce a simulation report showing where the skill matches your team's decisions, where it would have escalated, and where your written policy contradicts actual behavior.

The output is an approved workflow specification your team can use as the source of truth for both manual operations and future AI agent execution.

### Who is this for?

Controllers, Heads of Finance Operations, and VPs of Finance at B2B SaaS and fintech companies with usage-based billing — typically those running on Stripe Billing, Metronome, Orb, m3ter, or Lago. The pain we solve is specific: credit memos, refunds, and billing adjustments that require manual finance review because support automation cannot be trusted with them.

Support Ops, Risk, and Compliance are stakeholders, but Finance owns the budget and the risk.

### How is this different from a support chatbot like Decagon or Sierra?

Support chatbots optimize for conversation deflection. We optimize for policy fidelity.

A support bot can answer "where is my refund?" but typically cannot issue a refund above a company's approval threshold without a human, because doing so safely requires comparing written policy to actual behavior, knowing the contract terms, getting Finance approval, and logging the right audit trail.

We are the layer that handles what comes after the conversation. Support agents and Skiljo are complementary — many of our customers also run a support chatbot.

### How is this different from workflow automation tools like Workato or Zapier?

Workflow automation tools execute deterministic workflows you already know how to specify. Skiljo extracts the decision logic in the first place — by parsing policy documents, mining historical behavior, surfacing contradictions, and asking the workflow owner structured questions to resolve ambiguity.

By the time a workflow is ready to automate, it has been simulated against your historical decisions and explicitly approved by Finance.

### How does the diagnostic work?

You give us:

- Your written refund, credit, or billing adjustment policy
- A sample of past support tickets or finance approvals (CSV export is fine)
- 30 minutes with the Controller or workflow owner

Within one week, we deliver:

- An extracted skill specification
- A historical simulation report showing match rate, escalation accuracy, and automation candidates
- A policy/practice contradiction report
- A runtime pilot recommendation

The diagnostic is delivered as a standalone artifact whether or not you continue. Many Controllers buy the diagnostic for the contradiction report alone.

### What does it cost?

- **Diagnostic:** $10,000–$25,000 one-time, sized to fit a Controller's discretionary budget
- **Continuous policy fidelity:** $3,000–$8,000/month, scoped by number of active workflow skills
- **Governed runtime:** Base fee + per-executed workflow, available after the simulation report has earned trust

### Why pay monthly after the diagnostic?

Three reasons:

1. **Policy drift.** Every pricing change, product launch, or contract negotiation creates new edge cases. We catch them on a quarterly cadence.
2. **Expanding coverage.** Most customers start with refunds and quickly want the same treatment for credits, billing adjustments, and enterprise exceptions.
3. **Audit evidence.** Versioned skill specs and quarterly contradiction reports become the artifact Finance hands to auditors when asked why a specific credit was approved.

### What about data privacy and security?

For the MVP, we work from customer-provided exports rather than live integrations. This keeps the initial surface area small and avoids deep system access until the customer is ready for the governed runtime.

Production runtime is opt-in and is built on per-skill delegated authority — each skill defines exactly which data it can read, which actions it can take, and which actions require human approval.

### How long does deployment take?

One week from data access to first simulation report. For the runtime tier, expect four to six weeks of security review, integration approvals, and Finance sign-off before any agent executes in production.

### What if our written policy is wrong?

That is the most common finding. Our contradiction report surfaces these cases explicitly, and the recommended resolution is typically to rewrite the policy to match what is actually working — not to force operations back to a policy nobody is following. We have seen this be the highest-value deliverable from the diagnostic alone.

### What happens to the skill spec if we stop using Skiljo?

You keep it. The skill spec is delivered as a structured JSON/YAML artifact that is yours to use, modify, or repurpose. We see this as the right answer for a system of record that touches Finance — lock-in should come from continuous value, not portability friction.

---

## Internal FAQ

### Why now?

Three things are converging:

1. AI agents have crossed the capability threshold where they can hold conversations and call tools, but they fail on company-specific judgment. The bottleneck is no longer capability — it is governance.
2. Usage-based billing is now mainstream in B2B SaaS and fintech. Every company on Stripe Billing, Metronome, Orb, m3ter, or Lago is generating credit memos at a rate flat-rate SaaS never did, and Controllers are drowning in manual adjustments.
3. AI support agents (Decagon, Sierra, Maven) have proven that companies will buy AI for customer-facing work. But these products explicitly stop at the conversation. Finance-sensitive workflows are the next layer, and there is no incumbent.

### Why us?

We are the team willing to start with the unsexy part — extracting policy from documents, mining contradictions from tickets, and earning Finance trust before touching the runtime. Most AI startups want to ship the runtime first. We want to ship the trust layer first, because Finance buyers will not approve a runtime they cannot audit.

### What's our wedge?

Credit and refund workflows in usage-based billing.

This is narrower than "fintech," narrower than "B2B SaaS," and narrower than "refunds." We pick this slice because:

- Pain is weekly, not quarterly
- Policy is ambiguous (proration, overage, contract-specific terms)
- Controllers feel the pain directly and own discretionary budget
- The work creates audit and revenue-recognition risk
- Support chatbots explicitly cannot touch it

### What's our biggest risk?

Buyer pain is not strong enough. The Controller might agree the problem exists but not feel it acutely enough to pay $10K–$25K for a diagnostic.

Mitigation: 10–20 buyer interviews before launching, prioritizing customers with active audit or reconciliation pain. If three of ten Controllers say "I'd need to involve procurement above $15K," we drop the diagnostic ceiling. If fewer than three of ten say "yes, I'd pay for this report," we revisit the wedge before building.

### Why won't Decagon or Sierra just build this?

They could. They probably will not, because:

- Their product metric is conversation deflection, not policy fidelity
- Their buyer is Support Ops / VP CX, not Finance
- Their distribution model (sell to support leaders) does not naturally extend to Finance procurement
- Adding governance, simulation, and Finance approval gates pulls product velocity away from their core conversation surface

The risk is real but bounded. If Decagon or Sierra builds a workflow-governance product, it will likely be a feature inside their existing platform. We are betting that Finance buyers want a system of record that is not coupled to a specific support vendor — and that this becomes the durable position.

### What's our defensibility?

Three things compound:

1. **Customer-specific policy graphs.** Every quarter of re-simulation deepens our model of how a specific customer actually operates. Switching costs grow with skill count.
2. **Approved workflow history.** Every Finance-approved amendment, resolved contradiction, and versioned skill becomes a system-of-record artifact. Finance and Audit treat this as the equivalent of a closing checklist — replacing it means losing institutional memory.
3. **The diagnostic-to-runtime trust curve.** Customers who graduate from diagnostic to recurring to runtime have an 18-month relationship before runtime even starts. That is a moat competitors cannot skip past.

### What's the path from diagnostic to runtime?

```text
Month 1:     Paid diagnostic delivered. Controller sees contradiction report.
Month 2–3:   Customer rewrites policy to match approved behavior. Subscribes to
             continuous policy fidelity to lock in the new state.
Month 4–9:   Customer adds 2–4 more workflow skills. Quarterly re-simulation
             catches drift from product/pricing changes.
Month 9–12:  Customer signs runtime pilot for the narrowest, lowest-risk
             automation slice. 4–6 weeks of security review.
Month 12+:   Runtime expands. Pricing transitions to base + per-execution.
```

The recurring tier is the bridge. Without it, the gap between "I bought a diagnostic" and "I trust your agent to touch the ledger" is too wide.

### What's the financial picture?

Early (Customers 1–10):

- $10K–$25K diagnostic × 10 = $100K–$250K
- 20–40% gross margin (founder-led delivery)
- Goal: prove repeatability, productize Q&A and simulation

Mid (Customers 10–25):

- Diagnostic + $3K–$8K/month recurring on most customers
- 40–60% gross margin
- Goal: 70%+ recurring revenue share, ARR > $1M

Mature (Customers 25+):

- Recurring + runtime on majority of base
- 70%+ gross margin
- Outcome-based runtime pricing drives expansion

### What does success look like in 12 months?

- 25–40 paid diagnostics delivered
- 10–15 customers on continuous policy fidelity contracts
- 3–5 customers in narrow runtime pilots
- ARR in the $750K–$1.5M range, weighted toward recurring
- At least one customer publicly referenceable for the contradiction report

### What does failure look like, and what would we change?

Two failure modes:

1. **Diagnostic does not convert to recurring.** If fewer than 40% of diagnostic customers continue to month 4, the recurring value story is weaker than we think. Response: lean harder into runtime and treat the recurring tier as optional.
2. **Wedge is too narrow.** If we cannot find 25 paying customers in usage-based B2B SaaS / fintech within 12 months, the sub-segment is too small or the pain is mis-targeted. Response: expand to flat-rate B2B SaaS or marketplaces, but only after exhausting the original wedge.

### What are we explicitly not doing?

- Building a support chatbot
- Building enterprise search
- Building a generic workflow automation platform
- Building 10 integrations before customer 10
- Building a multi-agent platform
- Building a workflow marketplace

Depth on one workflow beats breadth across many. The first 10 customers all buy the same diagnostic for the same workflow at the same buyer persona.