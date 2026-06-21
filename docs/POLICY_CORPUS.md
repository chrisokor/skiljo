# Skiljo Policy Corpus — Research Notes

> **Purpose:** A curated set of real public refund, credit, and billing policies for use as extraction targets during Skiljo's build. These are the inputs you'll hand-label in week 2 (commit 24) and expand in week 5 (commit 51).
>
> **Methodology:** Policies were selected to (1) reflect Skiljo's ICP (usage-based B2B SaaS and fintech), (2) span a range of structural complexity from simple to gnarly, and (3) include at least one policy with known contradictions or interpretive ambiguity to stress-test contradiction detection.
>
> **Copyright note:** Only URLs and high-level characterizations are recorded here. Full policy text is fetched at extraction time, not redistributed.

---

## Summary table

| # | Company | Policy type | URL | Complexity | Why it matters |
|---|---|---|---|---|---|
| 1 | Stripe | Subscription + entitlement + overage | stripe.com/legal/subscription-policy | Medium | ICP-perfect: usage-based with entitlements, overages, and explicit non-refund language |
| 2 | Stripe Docs | Foundations/Expansion/Scale plan terms | docs.stripe.com/bundled-pricing/terms | Medium | Companion to #1; cleaner structure, easier to extract |
| 3 | Amazon EC2 | SLA with tiered service credits | aws.amazon.com/compute/sla/ | High | Tiered uptime thresholds, region-level + instance-level dual SLA, strict claim format |
| 4 | Amazon S3 | SLA with tiered service credits | aws.amazon.com/s3/sla/ | Medium | Sibling of #3; useful for testing extraction consistency across similar policies |
| 5 | AWS Audit Manager | SLA | aws.amazon.com/audit-manager/sla/ | Medium | Smaller, cleaner; good baseline for AWS family |
| 6 | OpenAI | Service Credit Terms | openai.com/policies/service-credit-terms/ | Medium | Non-refundable credits, expiration logic, transfer prohibitions |
| 7 | OpenAI | Services Agreement (enterprise) | openai.com/policies/services-agreement/ | High | B2B enterprise contract language, minimum commitments, IP indemnification refunds |
| 8 | Twilio | Terms of Service | twilio.com/en-us/legal/tos | Medium | Usage-based billing, 60-day dispute window, late-fee logic |
| 9 | Vercel | Terms of Service | vercel.com/legal/terms | Medium | Plan tiers, anomalous-use override, non-Vercel service ceasing |
| 10 | Vercel | Pro Plan billing docs | vercel.com/docs/plans/pro-plan | High | Hybrid model: subscription + included allocation + monthly credit + on-demand overage |
| 11 | Notion | Refund policy | notion.com/help/refunds | Low-Medium | Monthly vs annual windows, EU/UK regional override, accidental-member refunds |
| 12 | Shopify | Plan refund policy | help.shopify.com/en/manual/your-account/manage-billing/refund-policy-subscriptions | Medium | **Known policy/practice contradiction** — written policy says no refunds, actual practice is case-by-case |
| 13 | Shopify Plus | Plus Terms | shopify.com/plus/legal/terms | Medium | Enterprise-tier contract language |
| 14 | Steam | Refund policy | store.steampowered.com/steam_refunds/ | High | Complex conditional logic across product types (games, DLC, bundles, pre-purchase, video, VAC bans) |
| 15 | Google Cloud | Compute Engine SLA | cloud.google.com/compute/sla | High | Cross-vendor sibling of #3; conditional credit ladders by instance config; broader family of related SLAs |
| 16 | Cloudflare | Business SLA + Billing Policy | cloudflare.com/business-sla/ + developers.cloudflare.com/billing/understand/billing-policy/ | High | Two-document layered policy; explicit credit formula; tier-gated SLA applicability |
| 17 | DigitalOcean | Droplets SLA (with sibling product SLAs) | digitalocean.com/sla/cpu-droplets (+ family) | Medium-High | Same-vendor policy family with variant thresholds and notification windows; intra-vendor drift |
| 18 | Square | Payment Terms (merchant-side) | squareup.com/us/en/legal/general/payment-annotated | High | Merchant-side refund + chargeback semantics; reserve withholding; meta-rule about policy disclosure |
| 19 | Atlassian | Refund policy | support.atlassian.com/subscriptions-and-billing/docs/request-a-refund/ | Low-Medium | Window-based refunds split by cadence; renewals/upgrades carve-out |
| 20 | GitHub | Terms of Service (payments section) | docs.github.com/en/site-policy/github-terms/github-terms-of-service | Medium | **Cross-document contradiction** — absolute no-refund ToS vs. operational Copilot refund flows |

---

## Tier 1: ICP-aligned (usage-based B2B SaaS and fintech)

These are the most important examples because they match Skiljo's actual target customer. Hand-labeling these well is the highest-leverage time investment in week 2.

### 1. Stripe — Subscription Pricing and Cancellation Policy
**URL:** https://stripe.com/legal/subscription-policy

Stripe is the prototype customer for Skiljo. This policy combines a flat subscription fee with metered overage charges, defines entitlements as usage caps, and includes explicit "fees are non-refundable, no prorated refunds" language that creates a clear extraction target. It also covers plan changes (upgrade/downgrade timing), suspension conditions, and payment failures.

**Extraction challenges:** The policy uses defined terms ("Subscription Plan," "Entitlement," "Overage Fees") that the extractor must track consistently. The non-refund language has hedge clauses ("except as required by law") that matter for accuracy.

**Good for testing:** entitlement extraction, overage rule extraction, plan-change timing rules.

### 2. Stripe Docs — Foundations/Expansion/Scale plan terms
**URL:** https://docs.stripe.com/bundled-pricing/terms

A cleaner companion to the legal policy above, written in product-documentation voice rather than legal voice. The structural content overlaps significantly with #1 but the language is more accessible.

**Extraction challenges:** Lower than #1; this is a good baseline.

**Good for testing:** comparing extraction quality across two stylistic registers describing similar policy content. If Skiljo extracts the same rules from both, that's a strong consistency signal.

### 3. Amazon EC2 — SLA
**URL:** https://aws.amazon.com/compute/sla/

The single best AWS SLA for extraction testing because it has both a region-level SLA and an instance-level SLA with different credit calculations. The credit tiers are: less than 99.99% but ≥99.0% → 10%, less than 99.0% but ≥95.0% → 30%, less than 95.0% → 100%. There's also an automatic instance-level credit for outages over six minutes that doesn't require a claim.

**Extraction challenges:** Numerical thresholds (uptime percentages, credit percentages, six-minute auto-credit), dual SLA structure, strict claim format requirements ("SLA Credit Request" in subject line, specific data in body, deadline of "end of the second billing cycle after which the incident occurred").

**Good for testing:** tiered threshold extraction, multi-policy-in-one-document handling, claim-format extraction.

### 4. Amazon S3 — SLA
**URL:** https://aws.amazon.com/s3/sla/

Structurally similar to #3 but for object storage. Includes a $1 USD minimum claim threshold and non-transferability rules.

**Extraction challenges:** Lower than EC2 because there's only one SLA tier structure.

**Good for testing:** consistency with EC2 extraction — if Skiljo extracts the same shape of rule structure across both, the extractor is robust to surface variation.

### 5. AWS Audit Manager — SLA
**URL:** https://aws.amazon.com/audit-manager/sla/

The smallest AWS SLA, structurally identical to the others. Useful as a third sibling for consistency testing.

**Good for testing:** baseline AWS extraction, low-noise sample.

### 6. OpenAI — Service Credit Terms
**URL:** https://openai.com/policies/service-credit-terms/

Defines API credits as non-refundable, with a one-year expiration from purchase date. Prohibits transfer, sale, or gifting. Explicit consequence chain: attempted transfers may result in revocation of credits and account termination "without refund."

**Extraction challenges:** Distinguishing "non-refundable" rules from "exception conditions" (the "except where required by law" hedge). Multi-step consequence chains.

**Good for testing:** consequence/penalty extraction, exception-clause handling.

### 7. OpenAI — Services Agreement (enterprise)
**URL:** https://openai.com/policies/services-agreement/

Enterprise-flavored contract language with minimum commitments, late-fee structure, IP-infringement refund triggers, and termination-with-refund conditions (for example, infringement claims where the service can't be reasonably replaced).

**Extraction challenges:** Conditional refund triggers tied to events ("if OpenAI reasonably believes the service is likely to become subject of an infringement Claim"), minimum-commitment non-cancellation logic.

**Good for testing:** event-triggered refund rules, contractual minimum extraction.

### 8. Twilio — Terms of Service
**URL:** https://www.twilio.com/en-us/legal/tos

Pure usage-based billing. The interesting parts for extraction are the 60-day billing dispute window, the 15-day grace period before late fees, the 1.5% monthly late fee, and the suspension-on-non-payment logic.

**Extraction challenges:** Multiple time windows (60 days, 15 days), conditional late fee rate (lesser of 1.5%/month or legal maximum), procedure-style rules ("you must notify us in writing within X days").

**Good for testing:** time-window extraction, billing-dispute rule extraction.

### 9. Vercel — Terms of Service
**URL:** https://vercel.com/legal/terms

Notable feature: explicit clause allowing Vercel to automatically charge for "elevated, irregular, high or anomalous use" at its sole discretion. This is a fascinating extraction target because the trigger is genuinely ambiguous — what counts as "anomalous"?

**Extraction challenges:** Ambiguous trigger conditions that resist clean rule encoding. This is the kind of policy that should produce an LLM-assisted zone rule rather than a deterministic one.

**Good for testing:** zone classification (this should NOT classify as deterministic), ambiguity detection.

### 10. Vercel — Pro Plan billing documentation
**URL:** https://vercel.com/docs/plans/pro-plan

The richest single document in the corpus. Hybrid billing model: $20/seat/month + included allocation (1TB Fast Data Transfer, 10M Edge Requests) + $20 monthly usage credit + on-demand overage at per-unit rates. Notification triggers at 75% credit consumption. Spend management with default $200 budget cap.

**Extraction challenges:** Multiple billable resources each with their own unit rates, credit-then-overage cascade logic, notification thresholds, default vs. configurable spend caps.

**Good for testing:** complex multi-resource billing model extraction. If Skiljo handles this well, it can handle most usage-based SaaS policies.

### 15. Google Cloud — Compute Engine SLA
**URL:** https://cloud.google.com/compute/sla

Cross-vendor sibling of AWS EC2 (#3) with different structural choices. Tiered uptime credits at different thresholds, a 50% of monthly bill cap, a 30-day claim notification window, and an enumerated exclusions list with multiple sub-clauses. The "Instances in Multiple Zones" vs "Single Instance" distinction creates a conditional with different credit ladders for each branch. Cross-references the broader Google Cloud SLA family (Cloud Storage, BigQuery, Cloud Run, Cloud Functions, Cloud Observability, Identity Platform) — siblings with slightly different terms, useful for the same kind of consistency testing as the AWS family.

**Extraction challenges:** Conditional SLA-tier-based-on-instance-config logic, "30-day notification" vs AWS's "end of second billing cycle" framing (same intent, different shape).

**Good for testing:** cross-vendor structural comparison. If Skiljo extracts the same shape of tiered-credit rule from both AWS EC2 (#3) and Google Compute Engine but captures the different conditional triggers, the extractor is generalizing well across cloud SLA dialects.

### 16. Cloudflare — Business SLA + Billing Policy
**URLs:** https://www.cloudflare.com/business-sla/ and https://developers.cloudflare.com/billing/understand/billing-policy/ (plus enterprise variant at https://www.cloudflare.com/enterprise-support-sla/)

A two-document policy that pairs an explicit credit-calculation formula with a strict separate refund policy, creating layered logic. The SLA formula is `Service Credit = (Outage Period minutes × Affected Customer Ratio) ÷ Scheduled Availability minutes`, with a 12-month rolling cap of one month's cumulative fees and six enumerated exclusion categories (a–f). The billing policy independently states "FEES ARE NONREFUNDABLE" with a minimum one-month purchase obligation. Tier eligibility matters: Free and Pro plans get no SLA at all; Business gets the 100% uptime guarantee; Enterprise has a separate SLA with credit multipliers (10x or 25x) tied to which success-tier the customer purchased.

**Extraction challenges:** Two documents that interact — when does the SLA override the no-refund rule? Mathematical formula extraction rather than tiered table extraction (different shape from AWS/Google). Tighter 5-business-day notification window plus a separate formal-claim deadline. Tier-gated rule applicability (rules only apply if the customer is on a qualifying plan).

**Good for testing:** multi-document policy assembly, formula-vs-table credit logic, tier-gated rule activation. This is the policy where the compiler will most clearly demonstrate "rules don't live in one file" handling.

### 17. DigitalOcean — Droplets SLA (with sibling product SLAs)
**URLs:** https://www.digitalocean.com/sla/cpu-droplets (canonical), plus siblings at /sla/databases, /sla/doks, /sla/spaces, /sla/volumes, /sla/app-platform, /sla/regional-load-balancers, /sla/nat-gateway, /sla/container-registry, /sla/spaces-cold-storage

A family of per-product SLAs from one vendor that share a template but vary on key parameters: uptime thresholds (99.99% for Droplets and Volumes, 99.95% for App Platform / NAT Gateway / Container Registry, 99.95% vs 99.5% for Managed DBs depending on Standby Nodes config, 99.9% for Spaces and Regional Load Balancers) and notification windows (24 hours for some products, 30 days for others, "two billing cycles" for others). Same vendor, same template, but real cross-policy variance.

**Extraction challenges:** Family-level extraction — same underlying rule template instantiated with different parameters per product. The "with/without Standby Nodes" branching in Managed Databases is a clean conditional. The differing notification windows across siblings will trip a naive extractor that assumes one-vendor-one-policy.

**Good for testing:** policy-family handling, cross-product consistency detection within a single vendor, and contradiction detection for accidental policy drift (DigitalOcean's own siblings disagree on notification windows — is this intentional design or accidental drift? The extractor should surface the disagreement either way).

### 18. Square — Payment Terms (merchant-side)
**URL:** https://squareup.com/us/en/legal/general/payment-annotated

Merchant-side refund and chargeback semantics — the exact policy shape Skiljo's Controller/Finance Ops buyers need to encode for their own customer-facing operations. Concrete rules: a 120-day refund processing window from the date of original payment, a refund amount restriction ("cannot exceed the amount shown as the total on the original sales data, except by the exact amount required to reimburse the customer for postage"), explicit chargeback liability ("we may debit your linked bank account"), reserve withholding for likely chargebacks, and Recovery Authorizations for fees, fines, or penalties. Network Rules require the seller to disclose their own return/cancellation policy to customers at purchase time — a meta-rule about policy disclosure.

**Extraction challenges:** Multiple interlocking financial rules (refund limit + reserve withholding + chargeback debit + recovery authorization), conditional liability assignment (who pays when), and the meta-rule about policy disclosure to end customers. Contrasts well with Stripe (#1) — same general space, very different stance on seller risk.

**Good for testing:** financial-rule interlock extraction, seller-side vs platform-side rule disambiguation, and policy-about-policy rules (the disclosure requirement). Pair with Stripe (#1) for two-vendor payments comparison.

---

## Tier 2: B2B SaaS subscription

### 11. Notion — Refund policy
**URL:** https://www.notion.com/help/refunds

Compact but contains real structural variation: three-day refund window for monthly billing, thirty-day window for annual billing, EU/UK override to 14-day mandatory window, special-case refund for accidentally-added members.

**Extraction challenges:** Conditional windows based on billing cadence, regional regulatory overrides, exception-class refunds.

**Good for testing:** clean baseline with light conditional logic. The regional override is particularly interesting — the extractor needs to capture "EU users get different rules" as a top-level conditional.

### 12. Shopify — Plan refund policy
**URL:** https://help.shopify.com/en/manual/your-account/manage-billing/refund-policy-subscriptions

**This is the corpus's flagship contradiction-detection example.** The written policy says Shopify's Terms of Service do not allow refunds. But the help center explicitly describes time-window-based eligibility for case-by-case review by support. The official "no refunds" position contradicts the documented "we review eligible requests" practice.

**Extraction challenges:** Detecting the contradiction itself — both rules are stated in the same document but they don't agree. The extractor should produce two rules and a flag that they conflict, not silently pick one.

**Good for testing:** contradiction detection. If Skiljo's contradiction detector flags this, the feature works.

### 13. Shopify Plus — Plus Terms
**URL:** https://www.shopify.com/plus/legal/terms

Enterprise tier with stronger non-refund language tied to contract terms and prepaid fees.

**Good for testing:** enterprise-contract-flavored policy extraction.

### 19. Atlassian — Refund policy
**URL:** https://support.atlassian.com/subscriptions-and-billing/docs/request-a-refund/

Window-based refund policy with split terms by billing cadence (monthly: first paid month after trial; annual: 30 days from purchase) plus a clean carve-out class ("Cloud renewals and upgrades cannot be refunded"). Adjacent cancellation mechanics are documented separately at /docs/cancel-a-subscription/: a 15-day grace after billing-cycle-end for deactivation, immediate-on-cancellation for free tier. Different from Notion (#11) in two key ways — no regional override, and the renewals/upgrades carve-out is a different exception type than Notion's accidental-member refund.

**Extraction challenges:** Two parallel windows differentiated by billing cadence, a carve-out class for renewals and upgrades, and an operational-vs-policy split (refund eligibility in one doc, cancellation mechanics in another).

**Good for testing:** consistency with Notion (#11) on basic shape — both are window-based — while detecting that Atlassian has no regional override but does have a renewals carve-out. A robust extractor should produce structurally similar outputs with the variance correctly captured.

### 20. GitHub — Terms of Service (payments section)
**URL:** https://docs.github.com/en/site-policy/github-terms/github-terms-of-service (plus Marketplace billing at https://docs.github.com/en/enterprise-cloud@latest/apps/github-marketplace/selling-your-app-on-github-marketplace/billing-customers)

A second contradiction-detection candidate alongside Shopify (#12), but with a different shape. The ToS states an absolute position: "no refunds or credits for partial months of service, downgrade refunds, or refunds for months unused with an open Account … no exceptions will be made." But the operational reality, documented across GitHub Support flows for Copilot subscriptions, is a 30-day unused-subscription refund window plus case-by-case prorated refunds via the Virtual Agent. The Marketplace billing docs add a third layer: no refunds on downgrade, but the current plan remains active until end of the billing cycle.

**Extraction challenges:** Stated-vs-operational contradiction with a different signature than Shopify (#12). Shopify's contradiction is within a single document; GitHub's is across documents (ToS vs Support flows vs Marketplace docs). The extractor needs to surface "the ToS says X but the operational documentation says Y" as a multi-document contradiction.

**Good for testing:** cross-document contradiction detection. If Shopify (#12) tests intra-document contradiction and GitHub tests inter-document contradiction, both flavors are covered in the corpus.

---

## Tier 3: Variety / edge cases

### 14. Steam — Refund policy
**URL:** https://store.steampowered.com/steam_refunds/

Not B2B and not the ICP, but included because it's the densest conditional-logic policy I found anywhere. The core rule (14 days, 2 hours playtime) is simple, but the exceptions and special cases multiply: DLC (refundable if underlying game has <2 hours since DLC purchase, unless DLC was "consumed, modified, or transferred"), bundles (full refund only if no items transferred and combined usage <2 hours), pre-purchases (14-day window starts at release), early access (playtime counts even before release), video content (non-refundable except in bundles), VAC bans (forfeit refund rights), gifts (different rules for unredeemed vs. redeemed), and refund-history monitoring ("Steam tracks repeated refund requests").

**Extraction challenges:** Highest in the corpus. Multiple product types with different rules. Nested conditions. State-dependent conditions (DLC "consumed").

**Good for testing:** the upper bound of what the extractor can handle. If Steam's policy extracts cleanly, the extractor is robust to almost anything in the ICP.

---

## How to use this corpus

### For the initial week 2 hand-labeling (commit 24, 20 examples)

Pick the cleanest 8 single-rule examples first to build labeling muscle: Notion (#11), AWS S3 SLA (#4), AWS Audit Manager SLA (#5), Stripe Docs (#2), OpenAI Service Credit Terms (#6), Twilio (#8), Shopify Plus (#13), and one focused excerpt from Vercel Pro (#10).

Then label 8 harder examples that introduce structural complexity: Stripe legal (#1), Amazon EC2 (#3), OpenAI enterprise (#7), Vercel Terms (#9), Vercel Pro full (#10), Notion (re-labeled with the regional override as a separate rule, #11), Shopify subscription (#12), and one bundled excerpt from Steam (#14).

Reserve 4 examples from the harder set for the dev split — these become your iteration target.

### For the week 5 expansion (commit 51, expand to 60)

The 20 documents above can yield 60+ labeled examples because most contain multiple distinct rule clusters. Stripe's legal policy alone has 6+ extractable rule families (subscription terms, plan changes, suspension, payment, taxes, refund exceptions). Steam's policy has 8+ (base rule, DLC, bundles, pre-purchase, early access, video, VAC, gifts). Amazon EC2 has 3+ (region-level SLA, instance-level SLA, automatic instance credit). The DigitalOcean family (#17) is particularly productive: each of its 9 sibling product SLAs is its own labelable cluster, with the cross-sibling drift itself being an extractable observation.

Treat each document as a source for 3–8 labeled examples by breaking it into rule clusters and labeling each cluster independently.

### Hold-out discipline

The Steam policy (#14) and Shopify subscription policy (#12) should be reserved for the held-out test set in `data/eval/test/`. They're the two most valuable for measuring real-world extraction quality, and they're the most likely to be over-fit if you iterate against them.

In the expanded corpus, also consider reserving Cloudflare (#16) and DigitalOcean (#17) for the held-out set — they cover structural shapes (multi-document formula extraction, intra-vendor policy-family drift) not represented elsewhere in the corpus.

### What this corpus is missing

Healthcare billing, marketplace seller payouts, BNPL, and chargebacks are not represented. These are mentioned in the BRD as later expansion verticals but were out of scope for the portfolio corpus. If you decide to expand the corpus during the build, search for: Klarna merchant refund policy, Etsy seller protection program, DoorDash merchant refund policy, Plaid customer agreement.

Also missing: any policy in a language other than English. Anthropic and Vercel both have translated versions of some policies — if you want to test cross-lingual extraction, those are starting points.

### Companies considered but not included

Anthropic's own policies were considered but excluded because using your own provider's policies as training data has weird optics if you eventually pitch this to Anthropic. Same logic for Cursor, OpenAI's own competitive products.

Datadog, Snowflake, and MongoDB Atlas were considered but their public-facing refund language is thinner than the included examples — most of their billing policy is in private enterprise contracts.

Slack and Figma have refund policies but they're structurally similar to Notion (#11) and didn't add unique extraction challenges. HubSpot was a strong alternate for #19/#20 — its annual auto-renew + "no mid-contract cancellation" + pro-rated refund-on-material-degradation shape is a clean enterprise-SaaS pattern — but Square (#18) and GitHub (#20) won the spots on the strength of their financial-rule interlock and contradiction-detection value respectively. If a later expansion needs another enterprise-SaaS annual-contract example, HubSpot's Customer Terms at https://legal.hubspot.com/terms-of-service is the first stop.