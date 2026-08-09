"""Tests for LLM call cost estimation (plan #56 cleanup).

Verifies:
- Known model + token counts produce the expected dollar estimate
- Missing token counts (e.g. a cache hit) return None rather than a guess
- Unknown models return None rather than a fabricated estimate
"""

from skiljo_core.llm.pricing import estimate_cost_usd


def test_estimate_cost_for_known_model() -> None:
    # claude-sonnet-4-6: $3.00/$15.00 per 1M tokens
    cost = estimate_cost_usd("claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 18.0


def test_estimate_cost_scales_with_token_counts() -> None:
    cost = estimate_cost_usd("claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
    # (1000 * 3.00 + 500 * 15.00) / 1_000_000
    assert cost == round((1000 * 3.00 + 500 * 15.00) / 1_000_000, 6)


def test_estimate_cost_none_when_input_tokens_missing() -> None:
    assert estimate_cost_usd("claude-sonnet-4-6", input_tokens=None, output_tokens=10) is None


def test_estimate_cost_none_when_output_tokens_missing() -> None:
    assert estimate_cost_usd("claude-sonnet-4-6", input_tokens=10, output_tokens=None) is None


def test_estimate_cost_none_for_unknown_model() -> None:
    assert estimate_cost_usd("some-future-model", input_tokens=100, output_tokens=100) is None


def test_estimate_cost_for_haiku() -> None:
    # claude-haiku-4-5: $1.00/$5.00 per 1M tokens
    cost = estimate_cost_usd("claude-haiku-4-5", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 6.0
