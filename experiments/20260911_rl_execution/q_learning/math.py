"""Training-label and support calculations; no environment or neural dependencies."""
from __future__ import annotations

import math
from collections.abc import Sequence

T0_SECONDS = 1000.0
FAILURE_PENALTY = 100.0


class InvalidSupport(ValueError):
    """No finite legal decision exists; callers must invoke their guarded fallback."""


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric, not boolean")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def normalized_rewards(
    costs_s: Sequence[float], true_source_count: int, *, failed: bool = False
) -> tuple[float, ...]:
    """Label a completed trajectory exactly once using trainer-only N.

    A failure penalty belongs only to the last true-terminal transition.
    An episode without learning transitions has no policy labels.
    """
    if isinstance(true_source_count, bool) or not isinstance(true_source_count, int):
        raise ValueError("true_source_count must be a positive integer trainer label")
    if not 1 <= true_source_count <= 16:
        raise ValueError("true_source_count must lie in [1, 16], including registered curricula")
    if not isinstance(failed, bool):
        raise ValueError("failed must be a true-terminal boolean")
    costs = tuple(_finite(x, "cost") for x in costs_s)
    if any(x < 0 for x in costs):
        raise ValueError("costs must be nonnegative actual elapsed virtual seconds")
    rewards = [-x / (T0_SECONDS * true_source_count) for x in costs]
    if failed and rewards:
        rewards[-1] -= FAILURE_PENALTY
    return tuple(rewards)


def undiscounted_returns(rewards: Sequence[float]) -> tuple[float, ...]:
    result = [0.0] * len(rewards)
    running = 0.0
    for i in range(len(rewards) - 1, -1, -1):
        running += _finite(rewards[i], "reward")
        result[i] = running
    return tuple(result)


def masked_probabilities(scores: Sequence[float], valid: Sequence[bool]) -> tuple[float, ...]:
    if len(scores) != len(valid):
        raise ValueError("scores and mask lengths differ")
    indices = [i for i, yes in enumerate(valid) if yes]
    if not indices:
        raise InvalidSupport("all candidates are masked")
    finite = {i: _finite(scores[i], "valid score") for i in indices}
    maximum = max(finite.values())
    weights = {i: math.exp(value - maximum) for i, value in finite.items()}
    normalizer = math.fsum(weights.values())
    return tuple(weights.get(i, 0.0) / normalizer for i in range(len(scores)))


def behavior_support(
    probabilities: Sequence[float], valid: Sequence[bool], teacher_index: int,
    *, kappa: float = 0.1,
) -> tuple[bool, ...]:
    """Relative behavior gate, not a confidence region or safety certificate."""
    if len(probabilities) != len(valid):
        raise ValueError("probability and mask lengths differ")
    if not 0.0 <= kappa <= 1.0 or not math.isfinite(kappa):
        raise ValueError("kappa must lie in [0, 1]")
    indices = [i for i, yes in enumerate(valid) if yes]
    if not indices:
        raise InvalidSupport("all candidates are masked")
    probs = [_finite(probabilities[i], "behavior probability") for i in indices]
    if any(p < 0 or p > 1 for p in probs) or max(probs) <= 0:
        raise InvalidSupport("legal behavior probabilities are invalid or all zero")
    threshold = kappa * max(probs)
    support = [bool(valid[i] and probabilities[i] >= threshold) for i in range(len(valid))]
    if 0 <= teacher_index < len(valid) and valid[teacher_index]:
        support[teacher_index] = True
    return tuple(support)


def masked_argmax(values: Sequence[float], valid: Sequence[bool]) -> int:
    if len(values) != len(valid):
        raise ValueError("value and mask lengths differ")
    indices = [i for i, yes in enumerate(valid) if yes]
    if not indices:
        raise InvalidSupport("no candidate in support")
    checked = {i: _finite(values[i], "supported value") for i in indices}
    # max retains the first stored candidate on a tie; identity is never regenerated.
    return max(indices, key=checked.__getitem__)


def double_q_target(
    reward: float, terminated: bool, next_online: Sequence[float] | None = None,
    next_target: Sequence[float] | None = None, next_support: Sequence[bool] | None = None,
) -> float:
    """Gamma=1 target. A true terminal never inspects any next-state object."""
    reward = _finite(reward, "reward")
    if not isinstance(terminated, bool):
        raise ValueError("terminated must be boolean")
    if terminated:
        return reward
    if next_online is None or next_target is None or next_support is None:
        raise ValueError("nonterminal transition requires its saved next candidate values")
    if len(next_target) != len(next_online):
        raise ValueError("online and target candidate order/length differ")
    chosen = masked_argmax(next_online, next_support)
    return reward + _finite(next_target[chosen], "selected target value")
