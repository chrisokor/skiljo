"""Cost estimation for logged LLM calls (plan #56 cleanup: resolves the
``cost_estimate_usd`` TODO in ``llm/logging.py``).

Anthropic prices per-model, per-million-tokens, with separate input/output
rates. This module holds a small static rate table for the models this
project actually calls (see ``config.DEFAULT_MODEL`` and
CLAUDE.md "Model selection is env-configurable per pipeline stage") and a
pure function to turn a (model, input_tokens, output_tokens) triple into a
dollar estimate.

Rates are current as of the model catalog this project targets. They are
not fetched live — Anthropic does not expose per-token pricing via the API
(the Models API returns capabilities, not price). If a call uses a model
not in the table, ``estimate_cost_usd`` returns ``None`` rather than
guessing — an absent estimate is honest; a wrong one is worse than none.
"""

from __future__ import annotations

# (input $ per 1M tokens, output $ per 1M tokens)
_RATES_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-opus-4-1": (15.00, 75.00),
}


def estimate_cost_usd(
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    """Estimate the dollar cost of one LLM call.

    Returns ``None`` when token counts are unavailable (e.g. a cache hit,
    which makes no API call) or when ``model`` has no known rate — callers
    should leave ``cost_estimate_usd`` unset in that case rather than
    persisting a fabricated number.
    """
    if input_tokens is None or output_tokens is None:
        return None

    rates = _RATES_PER_MILLION_TOKENS.get(model)
    if rates is None:
        return None

    input_rate, output_rate = rates
    cost = (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
    return round(cost, 6)
