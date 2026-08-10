"""Statistical significance testing for detected contradictions (scope A6).

The contradiction detector (``skiljo_core.simulation.contradictions``) flags
clusters whose divergence rate exceeds a bare frequency threshold. That is
enough to rank candidates but says nothing about whether the divergence is
distinguishable from ordinary noise around the system's baseline error rate.

This module adds that statistical layer: an exact two-sided binomial test.

H0: the observed divergence count is consistent with random variation around
    ``base_error_rate`` (ordinary noise, not a systematic policy violation).
H1: the observed divergence count is a systematic divergence from written
    policy (a genuine planted contradiction).

Implemented as a small pure-Python exact binomial test (mirroring
``scipy.stats.binomtest``'s two-sided method) rather than adding scipy as a
dependency for one function -- consistent with the project's "no
infrastructure beyond the design" stance.
"""

from __future__ import annotations

import math
from typing import Any

_DEFAULT_SIGNIFICANCE_LEVEL = 0.05
_DEFAULT_MIN_CLUSTER_SIZE = 50


def _binomial_pmf(k: int, n: int, p: float) -> float:
    """P(X = k) for X ~ Binomial(n, p)."""
    if p <= 0.0:
        return 1.0 if k == 0 else 0.0
    if p >= 1.0:
        return 1.0 if k == n else 0.0
    return math.comb(n, k) * (p**k) * ((1 - p) ** (n - k))


def binomial_test_two_sided(k: int, n: int, p: float) -> float:
    """Exact two-sided binomial test p-value for observing ``k`` successes in
    ``n`` trials under null hypothesis success probability ``p``.

    Sums the probability mass of every outcome at least as extreme as the
    observed outcome (mass <= observed mass, within a small relative
    tolerance to avoid floating-point edge cases) -- the same definition
    ``scipy.stats.binomtest`` uses for its two-sided test.
    """
    if n == 0:
        return 1.0
    k = max(0, min(k, n))
    observed_mass = _binomial_pmf(k, n, p)
    tolerance = observed_mass * (1 + 1e-7)
    return sum(
        mass for kk in range(n + 1) if (mass := _binomial_pmf(kk, n, p)) <= tolerance
    )


def binomial_test_contradiction(contradiction: dict[str, Any]) -> dict[str, Any]:
    """Test whether a candidate contradiction's divergence is statistically
    significant, i.e. distinguishable from the base error rate.

    Args:
        contradiction: dict with keys:
            - ``cluster_size`` (int): number of tickets in the cluster.
            - ``frequency`` (float): observed divergence rate (0-1).
            - ``base_error_rate`` (float): null-hypothesis error rate.
            - ``divergence_count`` (int, optional): exact number of
              divergent tickets. When omitted, derived from
              ``round(cluster_size * frequency)``.
            - ``min_cluster_size`` (int, optional): minimum cluster size
              for the result to be considered statistically supported.
              Defaults to 50 -- large enough for the binomial test to have
              real power; independent of the detector's own (much smaller)
              structural min_cluster_size used to decide whether a cluster
              is worth evaluating at all.

    Returns:
        dict with ``p_value``, ``supported``, ``divergence_count``, and
        ``base_error_rate``.
    """
    cluster_size = contradiction["cluster_size"]
    base_error_rate = contradiction["base_error_rate"]
    min_cluster_size = contradiction.get("min_cluster_size", _DEFAULT_MIN_CLUSTER_SIZE)

    divergence_count = contradiction.get("divergence_count")
    if divergence_count is None:
        divergence_count = round(cluster_size * contradiction["frequency"])

    p_value = binomial_test_two_sided(divergence_count, cluster_size, base_error_rate)

    return {
        "p_value": p_value,
        "supported": p_value < _DEFAULT_SIGNIFICANCE_LEVEL and cluster_size >= min_cluster_size,
        "divergence_count": divergence_count,
        "base_error_rate": base_error_rate,
    }
