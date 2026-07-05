# Week 3 Task 5 — Contradiction Detection

## What was built

A contradiction detector that identifies systematic divergences between the skill's decisions and ground-truth outcomes. It clusters tickets by (amount_band, customer_segment), measures divergence rate per cluster, and flags clusters where divergence exceeds a threshold.

**Files created:**
- `packages/core/src/skiljo_core/simulation/contradictions.py` — `Contradiction` dataclass, `_amount_band()` helper, `detect_contradictions()`
- `packages/core/tests/test_contradictions.py` — 4 tests covering: all-match (no contradictions), above-threshold detection, below-min-cluster-size, and below-threshold rate
- `packages/core/src/skiljo_core/simulation/__init__.py` — exports for `Contradiction` and `detect_contradictions`

## Why

After `simulate_batch` runs and produces results (skill decisions per ticket), we need to detect when the skill systematically diverges from ground truth at scale. Planted divergences (from the shadow policy) make this measurable: e.g., "VIP customers get approved 100% of the time when the skill says deny." A contradiction detector that recovers these planted patterns validates that the system can detect real policy gaps.

Without contradiction detection, simulation is just regression testing against the ground truth — it doesn't surface *where* and *why* the skill fails.

## Non-obvious concepts

**Cluster-based grouping strategy.** Tickets are grouped by `(amount_band, customer_segment)` — two dimensions that capture meaningful decision boundaries. Amount bands bucket refund size into ranges (0–50, 51–100, etc.) because decision logic often changes at thresholds. Customer segment (standard, VIP, etc.) is a categorical axis where policy frequently differs. Clustering prevents noisy signal: a single VIP ticket mismatch is noise; 5 VIP tickets all mismatching is a signal.

**Divergence rate as the key metric.** For each cluster, we count mismatches: tickets where `result.decision != ticket.ground_truth_decision`. The divergence rate is `len(diverged) / len(cluster)`. If the skill says "deny" but the ground truth says "approve" for 60% of VIP refunds in the $101–200 band, that's a 0.60 rate — well above the default 5% threshold.

**Threshold and min_cluster_size gates.** The threshold (default 5%) filters out noise — a single mismatch in a 20-ticket cluster is 5%, not worth reporting. The min_cluster_size (default 3) prevents spurious contradictions in tiny groups where one mismatch is statistically meaningless. Both are configurable so tests can exercise different regimes.

**Most-common divergence pair selection.** When a cluster diverges, there may be multiple (written, observed) decision pairs. For example, a cluster might have some "deny→approve" mismatches and some "approve→escalate" mismatches. We pick the most common pair using `Counter.most_common(1)[0]` and report that as the "written_decision" (what the skill says) and "observed_decision" (what ground truth says). This surfaces the primary contradiction; minor noise is ignored.

**Cluster key as dict, not tuple.** The `cluster_key` is stored as `{"amount_band": "101-200", "customer_segment": "vip"}` (dict) rather than a tuple, for readability in reports and API responses. The internal clustering uses tuples for efficiency (hashable, compact), but the output record uses a dict to be self-documenting.

**Affected ticket IDs as evidence trail.** The `affected_ticket_ids` list records which tickets drove the contradiction. This lets downstream analysis or human review drill into specific mismatches without re-running the detector.

## Where to look

- `skiljo_core/simulation/contradictions.py`:
  - `Contradiction` — the dataclass capturing one detected contradiction
  - `_amount_band(amount: float) -> str` — buckets refund amounts into ranges; thresholds are 50, 100, 200, 500
  - `detect_contradictions()` — orchestration: build ticket map, cluster by (amount_band, segment), compute divergence rate, apply filters, yield contradictions

- `skiljo_core/tests/test_contradictions.py`:
  - `test_no_contradictions_when_all_decisions_match()` — baseline: perfect skill, zero contradictions
  - `test_detects_contradiction_above_threshold()` — VIP cluster with 100% divergence, all 5 tickets mismatched
  - `test_no_contradiction_below_min_cluster_size()` — clusters with 2 tickets (below min_cluster_size=3) are silently dropped
  - `test_no_contradiction_below_threshold()` — 5% divergence rate below 10% threshold is ignored

- `skiljo_core/simulation/__init__.py` — public exports of `Contradiction` and `detect_contradictions`

## Planted divergence linkage

The contradiction detector is designed to measure itself against the shadow policy's planted divergences. When tickets are generated with a `DivergenceSpec` (e.g., "VIP refunds over $500 approved 80% of the time even though the skill says deny"), the ground truth follows the shadow policy. When the skill is simulated, it produces "deny" results on those tickets. The detector clusters VIP tickets in the $500+ band and discovers 80% divergence — recovering the planted signal. This closure makes the detector's precision/recall mechanically testable without human judgment.
