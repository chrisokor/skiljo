# Policy Corpus — Source Texts

Raw policy source texts, distinct from `data/eval/` (which holds labeled
train/dev/test examples for the extraction eval harness — see
`data/eval/README.md`). Files here are verbatim excerpts from real public
policy documents, kept for exercising the extraction pipeline and, in
particular, the cross-document contradiction detector (commit A3) end to
end against real-world text rather than paraphrased eval fixtures.

## Files

- `shopify-tos.txt` — Shopify Terms of Service, Section 5 (Payment of Fees
  and Taxes) and Section 9.3 (POS Services): an absolute, unqualified
  no-refund position.
- `shopify-help-center.txt` — Shopify Help Center refund article for
  subscriptions: a support-reviewed, time-windowed, case-by-case exception
  process for the same subscription fees.
- `stripe-refund.txt` — Stripe Subscription Policy: flat subscription fee
  plus metered overage fees, with an explicit non-refund, no-proration
  cancellation clause. Single-document non-refund baseline (no companion
  exception document included).
- `cloudflare-abuse.txt` — Cloudflare Self-Serve Subscription Agreement:
  acceptable-use restrictions, discretionary suspension/termination, and a
  billing section that states fees are nonrefundable immediately before
  carving out a discretionary refund/credit exception in the same clause.
- `digitaloceam-usage.txt` — DigitalOcean Terms of Service Agreement:
  non-cancelable committed-usage purchases, account deactivation for
  nonpayment, and a non-refundable-fees-plus-acceleration termination
  clause.

Each file records its source URL and retrieval date in a header comment,
and notes where the task's originally suggested source URL was
unreachable (404) and which real, live URL was substituted instead.

## Why these five

This set is deliberately small and pairs one intra-vendor
policy-vs-practice contradiction (Shopify ToS vs. Shopify Help Center —
the corpus's flagship acceptance case per `docs/POLICY_CORPUS.md` entry
#12) with three single-document non-refund baselines (Stripe, Cloudflare,
DigitalOcean) that vary in how absolute their no-refund language is:
Stripe is unconditional with no stated exception; Cloudflare and
DigitalOcean each carry a narrow, undescribed carve-out ("in our sole
discretion" / "expressly agreed between the parties") that is *not* the
same as Shopify's documented case-by-case process. That gradient is useful
for testing whether the contradiction detector can distinguish "silent
discretionary carve-out" from "documented exception process" rather than
flagging both the same way.

The Cloudflare and DigitalOcean documents used here (Self-Serve
Subscription Agreement; Terms of Service Agreement) are intentionally
different documents from the Cloudflare Business SLA + Billing Policy and
DigitalOcean Droplets SLA family named in `docs/POLICY_CORPUS.md` entries
#16 and #17, which are reserved for the held-out `data/eval/test/` set.
This avoids any overlap with held-out eval content (system invariant 5 in
`CLAUDE.md`).

## Used for

Manual and integration testing of the cross-document contradiction
detector (A3). Acceptance case: Shopify ToS (`shopify-tos.txt`) vs.
Shopify Help Center (`shopify-help-center.txt`) — same decision surface
(can a merchant get a subscription fee refunded), materially different
stated processes.

These files are not consumed by any automated test in this repo; they are
a fixture corpus for manual runs of the extraction and cross-document
pipelines against real text.
