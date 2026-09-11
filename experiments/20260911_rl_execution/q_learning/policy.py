"""Behavior-supported inference and explicitly training-only exploration."""
from __future__ import annotations

import dataclasses
import math
import random
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .math import InvalidSupport, behavior_support, masked_argmax, masked_probabilities

FEATURE_RANGE_CONTRACT = "training_extrema_v2_clocks_physical_only"
CLOCK_NUMERICAL_TOLERANCE = 1e-6
CLOCK_FEATURES = {6: "elapsed_real_1200", 14: "remaining_real_1200"}
CLOCK_SKIP_REASON = "wall_clock_runtime_and_load_are_not_geometric_support"


@dataclass(frozen=True)
class FeatureBounds:
    """Observed feature extrema: an empirical out-of-range check, never confidence."""
    minima: dict[str, tuple[float, ...]]
    maxima: dict[str, tuple[float, ...]]
    snapshot_count: int = 0
    revision: int = 1
    gate_contract: str = FEATURE_RANGE_CONTRACT

    @classmethod
    def fit(cls, snapshots: Iterable[Mapping[str, Any]]) -> "FeatureBounds":
        minima: dict[str, list[float]] = {}
        maxima: dict[str, list[float]] = {}
        count = 0
        for snap in snapshots:
            count += 1
            for key in ("global_features", "channel_features", "candidate_features"):
                rows = [snap[key]] if key == "global_features" else snap[key]
                for row in rows:
                    values = [float(v) for v in row]
                    if not values or not all(math.isfinite(v) for v in values):
                        raise ValueError("feature bounds need finite observable features")
                    if key not in minima:
                        minima[key] = list(values)
                        maxima[key] = list(values)
                    elif len(values) != len(minima[key]):
                        raise ValueError("feature dimensions changed inside support data")
                    else:
                        minima[key] = [min(a, b) for a, b in zip(minima[key], values)]
                        maxima[key] = [max(a, b) for a, b in zip(maxima[key], values)]
        if count == 0:
            raise ValueError("feature bounds require actual recorded training snapshots")
        return cls({k: tuple(v) for k, v in minima.items()}, {k: tuple(v) for k, v in maxima.items()},
                   snapshot_count=count)

    def extend(self, snapshots: Iterable[Mapping[str, Any]]) -> "FeatureBounds":
        """Merge only newly executed training observations, never selection/test rows."""
        incoming = FeatureBounds.fit(snapshots)
        if (self.minima.keys() != incoming.minima.keys()
                or any(len(self.minima[k]) != len(incoming.minima[k]) for k in self.minima)):
            raise ValueError("feature dimensions changed while extending training range")
        return FeatureBounds(
            {k: tuple(min(a, b) for a, b in zip(self.minima[k], incoming.minima[k]))
             for k in self.minima},
            {k: tuple(max(a, b) for a, b in zip(self.maxima[k], incoming.maxima[k]))
             for k in self.maxima},
            snapshot_count=self.snapshot_count + incoming.snapshot_count,
            revision=self.revision + 1)

    def violations(self, snapshot: Mapping[str, Any], tolerance: float = 1e-6) -> list[dict]:
        """One diagnostic per offending field, with observed and training extrema."""
        from core.schema import (GLOBAL_FEATURE_NAMES, CHANNEL_FEATURE_NAMES,
                                 CANDIDATE_FEATURE_NAMES)
        names = dict(zip(("global_features", "channel_features", "candidate_features"),
                         (GLOBAL_FEATURE_NAMES, CHANNEL_FEATURE_NAMES, CANDIDATE_FEATURE_NAMES)))
        findings = []
        for key in ("global_features", "channel_features", "candidate_features"):
            rows = [snapshot[key]] if key == "global_features" else snapshot[key]
            lo, hi = self.minima[key], self.maxima[key]
            if any(len(row) != len(lo) for row in rows):
                findings.append({"group": key, "field": key + ".dimension",
                                 "reason": "dimension_mismatch", "training_dimension": len(lo),
                                 "observed_dimensions": sorted({len(row) for row in rows})})
                continue
            for j, (lower, upper) in enumerate(zip(lo, hi)):
                values = [float(row[j]) for row in rows]
                clock_field = key == "global_features" and j in CLOCK_FEATURES
                checked_lower, checked_upper = (0.0, 1.0) if clock_field else (lower, upper)
                slack = (CLOCK_NUMERICAL_TOLERANCE if clock_field else
                         tolerance * max(1.0, abs(checked_lower), abs(checked_upper)))
                invalid_rows = [i for i, value in enumerate(values)
                                if not math.isfinite(value) or value < checked_lower - slack
                                or value > checked_upper + slack]
                if invalid_rows:
                    finite_values = [v for v in values if math.isfinite(v)]
                    field = names[key][j] if j < len(names[key]) else str(j)
                    findings.append({"group": key, "feature_index": j, "field": key + "." + field,
                                     "reason": "invalid_physical_clock_range" if clock_field else "outside_training_range",
                                     "checked_min": checked_lower, "checked_max": checked_upper,
                                     "empirical_range_skipped": clock_field, "training_min": lower,
                                     "training_max": upper, "observed_min": min(finite_values, default=None),
                                     "observed_max": max(finite_values, default=None),
                                     "nonfinite_count": len(values) - len(finite_values),
                                     "offending_row_count": len(invalid_rows), "example_rows": invalid_rows[:3]})
        return findings

    def contains(self, snapshot: Mapping[str, Any], tolerance: float = 1e-6) -> bool:
        return not self.violations(snapshot, tolerance=tolerance)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FeatureBounds":
        if data.get("gate_contract") != FEATURE_RANGE_CONTRACT:
            raise ValueError("feature-range checkpoint contract differs; no implicit clock-gate migration")
        return cls({k: tuple(v) for k, v in data["minima"].items()},
                   {k: tuple(v) for k, v in data["maxima"].items()},
                   snapshot_count=int(data.get("snapshot_count", 0)),
                   revision=int(data.get("revision", 1)))


def safe_teacher_choice(snapshot: Mapping[str, Any], reason: str) -> dict[str, Any]:
    valid = snapshot["valid_mask"]
    teacher = snapshot["teacher_index"]
    if 0 <= teacher < len(valid) and valid[teacher]:
        return {"index": int(teacher), "metadata": {"selector": "q", "selection_reason": reason,
                "used_teacher": True, "behavior_support_is_confidence": False}}
    for i, (candidate, yes) in enumerate(zip(snapshot["candidates"], valid)):
        if yes and candidate.get("kind") == "fallback":
            return {"index": i, "metadata": {"selector": "q", "selection_reason": reason,
                    "used_teacher": False, "forced_fallback": True,
                    "behavior_support_is_confidence": False}}
    raise InvalidSupport("no valid teacher or fallback; controller must take over")


def feature_range_metadata(snapshot, feature_bounds):
    """Log clock observations separately while leaving their neural inputs intact."""
    clocks = []
    for j, name in CLOCK_FEATURES.items():
        value = float(snapshot["global_features"][j])
        finite = math.isfinite(value)
        clocks.append({"group": "global_features", "feature_index": j,
                       "field": "global_features." + name,
                       "observed_value": value if finite else None, "finite": finite,
                       "physical_min": 0.0, "physical_max": 1.0, "numerical_tolerance": CLOCK_NUMERICAL_TOLERANCE,
                       "physical_range_valid": finite and -CLOCK_NUMERICAL_TOLERANCE <= value <= 1.+CLOCK_NUMERICAL_TOLERANCE,
                       "empirical_minmax_skipped": True, "skip_reason": CLOCK_SKIP_REASON,
                       "training_min_recorded_only": feature_bounds.minima["global_features"][j] if feature_bounds else None,
                       "training_max_recorded_only": feature_bounds.maxima["global_features"][j] if feature_bounds else None})
    return {"feature_range_revision": feature_bounds.revision if feature_bounds else 0,
            "feature_range_snapshot_count": feature_bounds.snapshot_count if feature_bounds else 0,
            "feature_range_contract": FEATURE_RANGE_CONTRACT,
            "clock_feature_checks": clocks, "feature_range_is_geometric_support_guarantee": False}


def range_guard(snapshot, feature_bounds, *, enforce_bounds=True):
    if not enforce_bounds:
        return None
    if feature_bounds is None:
        result = safe_teacher_choice(snapshot, "unfitted_behavior_feature_range")
        result["metadata"].update(feature_range_metadata(snapshot, feature_bounds))
        return result
    violations = feature_bounds.violations(snapshot)
    if violations:
        clock_errors = sum(v.get("reason") == "invalid_physical_clock_range" for v in violations)
        reason = ("invalid_physical_clock_range" if clock_errors == len(violations)
                  else "invalid_clock_and_empirical_feature_range" if clock_errors
                  else "outside_behavior_feature_range")
        result = safe_teacher_choice(snapshot, reason)
        result["metadata"].update(feature_range_metadata(snapshot, feature_bounds))
        result["metadata"]["feature_range_violations"] = violations
        return result
    return None


def choose_q_action(snapshot, online, behavior, *, kappa=0.1, feature_bounds=None,
                    enforce_bounds=True):
    """Shared deployment and TD next-action rule over the saved candidate ordering."""
    guarded = range_guard(snapshot, feature_bounds, enforce_bounds=enforce_bounds)
    if guarded is not None:
        return guarded
    try:
        valid = snapshot["valid_mask"]
        probs = masked_probabilities(behavior, valid)
        support = behavior_support(probs, valid, snapshot["teacher_index"], kappa=kappa)
        chosen = masked_argmax(online, support)
        result = {"index": chosen, "metadata": {
            "selector": "q", "selection_reason": "supported_q_argmax",
            "candidate_id": snapshot["candidate_ids"][chosen],
            "used_teacher": chosen == snapshot["teacher_index"],
            "support_mask": list(support), "support_count": sum(support),
            "behavior_probability": probs[chosen], "selected_q": online[chosen],
            "behavior_support_is_confidence": False,
        }}
    except (ValueError, FloatingPointError, RuntimeError) as exc:
        result = safe_teacher_choice(snapshot, "invalid_q_or_support")
        result["metadata"]["error_type"] = type(exc).__name__
    result["metadata"].update(feature_range_metadata(snapshot, feature_bounds))
    return result


class QSelector:
    def __init__(self, network, support_model, *, device="cpu", kappa=0.1,
                 feature_bounds: FeatureBounds | None = None, enforce_bounds=True):
        if not 0 <= kappa <= 1:
            raise ValueError("kappa must lie in [0, 1]")
        self.network = network.to(device).eval()
        self.support_model = support_model.to(device).eval()
        self.device = device
        self.kappa = float(kappa)
        self.feature_bounds = feature_bounds
        self.enforce_bounds = bool(enforce_bounds)

    def __call__(self, snapshot):
        import torch
        from shared import batch_snapshots
        guarded = range_guard(snapshot, self.feature_bounds, enforce_bounds=self.enforce_bounds)
        if guarded is not None:
            return guarded
        try:
            with torch.no_grad():
                batch = batch_snapshots([snapshot], self.device)
                online, _ = self.network(**batch)
                behavior, _ = self.support_model(**batch)
            n = len(snapshot["candidate_ids"])
            return choose_q_action(snapshot, online[0, :n].detach().cpu().tolist(),
                                   behavior[0, :n].detach().cpu().tolist(), kappa=self.kappa,
                                   feature_bounds=self.feature_bounds, enforce_bounds=self.enforce_bounds)
        except (ValueError, FloatingPointError, RuntimeError) as exc:
            result = safe_teacher_choice(snapshot, "invalid_q_or_support")
            result["metadata"].update(feature_range_metadata(snapshot, self.feature_bounds))
            result["metadata"]["error_type"] = type(exc).__name__
            return result


class TrainingExplorer:
    """A seedable data-collection policy, never a deployment selector.

    First 128 training episodes: 80% teacher / 20% other valid actions, at most
    eight deviations per episode. Later: 90% supported Q / 10% other valid.
    The exact mixture probability is recorded for auditing, not used as PPO data.
    """
    training_only = True

    def __init__(self, q_selector: QSelector, *, seed: int = 0):
        self.q_selector = q_selector
        self.rng = random.Random(seed)
        self.episode_index: int | None = None
        self.deviations = 0

    def start_episode(self, episode_index: int) -> None:
        if isinstance(episode_index, bool) or not isinstance(episode_index, int) or episode_index < 0:
            raise ValueError("episode_index is an explicit training counter")
        self.episode_index = episode_index
        self.deviations = 0

    def __call__(self, snapshot):
        if self.episode_index is None:
            raise RuntimeError("start_episode must be called by the training runner")
        valid = [i for i, yes in enumerate(snapshot["valid_mask"]) if yes]
        if not valid:
            raise InvalidSupport("training exploration has no legal candidate")
        early = self.episode_index < 128
        teacher = snapshot["teacher_index"]
        if early:
            base_choice = safe_teacher_choice(snapshot, "early_teacher_mixture")
            base = base_choice["index"]
            alternatives = [i for i in valid if i != base]
            epsilon = 0.2 if self.deviations < 8 and alternatives else 0.0
        else:
            base_choice = self.q_selector(snapshot)
            base = base_choice["index"]
            alternatives = [i for i in valid if i != base]
            epsilon = 0.1 if alternatives else 0.0
        explored = bool(epsilon and self.rng.random() < epsilon)
        chosen = self.rng.choice(alternatives) if explored else base
        if early and chosen != teacher:
            self.deviations += 1
        probability = epsilon / len(alternatives) if explored else 1.0 - epsilon
        metadata = dict(base_choice.get("metadata", {}))
        metadata.update(feature_range_metadata(snapshot, self.q_selector.feature_bounds))
        if explored:
            # These describe the base policy, not the sampled alternative.
            for key in ("selected_q", "behavior_probability", "forced_fallback"):
                if key in metadata:
                    metadata["base_" + key] = metadata.pop(key)
        metadata["base_candidate_id"] = snapshot["candidate_ids"][base]
        metadata.update({"selector": "q_training_mixture", "training_only": True,
                         "candidate_id": snapshot["candidate_ids"][chosen],
                         "training_episode_index": self.episode_index,
                         "sample_probability": probability,
                         "sample_logprob": math.log(probability),
                         "explored_alternative": explored,
                         "deviations_this_episode": self.deviations,
                         "used_teacher": chosen == teacher,
                         "behavior_support_is_confidence": False})
        return {"index": chosen, "metadata": metadata}
