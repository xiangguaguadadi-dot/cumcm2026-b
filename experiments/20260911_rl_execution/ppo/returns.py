"""Training-only complete-episode labels in the common seconds-per-source unit.

This module has no environment or neural-network imports. N is accepted only at
terminal label construction; callers must never append it to policy snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Sequence


T0_SECONDS = 1000.0
FAILURE_PENALTY = 100.0


class TerminalKind(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    INCOMPLETE = "incomplete"


def _finite_nonnegative(value: float, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric, not bool")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return value


@dataclass(frozen=True)
class ReturnLabels:
    """A label for each actual sampled selector decision, never fallback actions."""

    returns: tuple[float, ...]
    normalized_costs: tuple[float, ...]
    normalized_tail: float
    terminal_penalty: float
    accounted_cost_s: float


def complete_episode_returns(
    decision_costs_s: Sequence[float],
    *,
    tail_time_s: float,
    true_n: int,
    terminal: TerminalKind | str,
    t0: float = T0_SECONDS,
    failure_penalty: float = FAILURE_PENALTY,
) -> ReturnLabels:
    """Compute undiscounted MC returns with one normalization and one penalty.

    decision_costs_s excludes the disjoint tail_time_s. A runner which already
    folded a fallback tail into the last macro cost must pass tail_time_s=0.
    Artificially truncated episodes are rejected instead of becoming cheap
    terminals. Empty decision lists are allowed: the tail is still accounted,
    but no synthetic policy decision or log probability is created.
    """
    terminal = TerminalKind(terminal)
    if terminal is TerminalKind.INCOMPLETE:
        raise ValueError("a complete real terminal is required; resume this episode")
    if isinstance(true_n, bool) or not isinstance(true_n, int) or not 1 <= true_n <= 16:
        raise ValueError("true_n is a terminal training label in [1, 16]")
    t0 = _finite_nonnegative(t0, "t0")
    if t0 == 0:
        raise ValueError("t0 must be strictly positive")
    penalty = _finite_nonnegative(failure_penalty, "failure_penalty")
    costs = tuple(_finite_nonnegative(x, "decision cost") for x in decision_costs_s)
    tail = _finite_nonnegative(tail_time_s, "tail_time_s")
    scale = t0 * true_n
    normalized_costs = tuple(-x / scale for x in costs)
    terminal_penalty = -penalty if terminal is TerminalKind.FAILURE else 0.0
    running_cost_s = tail
    returns = [0.0] * len(costs)
    for i in range(len(costs) - 1, -1, -1):
        running_cost_s = math.fsum((costs[i], running_cost_s))
        returns[i] = -running_cost_s / scale + terminal_penalty
    return ReturnLabels(
        tuple(returns), normalized_costs, -tail / scale,
        terminal_penalty, math.fsum(costs) + tail,
    )


def episode_equal_sum(per_episode_terms: Sequence[Sequence[float]]) -> float:
    """Reference actor aggregation: mean of episode sums, not means of means."""
    if not per_episode_terms:
        raise ValueError("at least one episode is required")
    return math.fsum(math.fsum(row) for row in per_episode_terms) / len(per_episode_terms)
