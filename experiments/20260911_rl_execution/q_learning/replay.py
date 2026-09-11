"""Immutable Q replay built from the shared raw episode schema, never an environment."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .math import normalized_rewards, undiscounted_returns


@dataclass(frozen=True)
class FrozenSnapshot:
    canonical_json: str
    sha256: str
    candidate_ids: tuple[str, ...]
    valid_mask: tuple[bool, ...]
    teacher_index: int

    @classmethod
    def capture(cls, snapshot: Mapping[str, Any] | Any) -> "FrozenSnapshot":
        if dataclasses.is_dataclass(snapshot):
            snapshot = dataclasses.asdict(snapshot)
        elif hasattr(snapshot, "to_dict"):
            snapshot = snapshot.to_dict()
        if not isinstance(snapshot, Mapping):
            raise TypeError("snapshot must be the shared JSON-serializable snapshot")
        # Canonical serialization copies the complete payload and rejects nonfinite values.
        encoded = json.dumps(dict(snapshot), sort_keys=True, separators=(",", ":"), allow_nan=False)
        data = json.loads(encoded)
        ids = tuple(data["candidate_ids"])
        valid = tuple(data["valid_mask"])
        teacher = data["teacher_index"]
        if not ids or len(set(ids)) != len(ids) or any(not isinstance(i, str) for i in ids):
            raise ValueError("snapshot needs unique string candidate IDs")
        if len(valid) != len(ids) or any(type(v) is not bool for v in valid):
            raise ValueError("snapshot valid_mask must align exactly with candidate IDs")
        if isinstance(teacher, bool) or not isinstance(teacher, int) or not 0 <= teacher < len(ids):
            raise ValueError("teacher_index must address the stored candidate order")
        candidates = data.get("candidates")
        if candidates is None or len(candidates) != len(ids):
            raise ValueError("complete candidate payloads must be stored")
        return cls(encoded, hashlib.sha256(encoded.encode()).hexdigest(), ids, valid, teacher)

    def thaw(self) -> dict[str, Any]:
        if hashlib.sha256(self.canonical_json.encode()).hexdigest() != self.sha256:
            raise ValueError("snapshot integrity check failed")
        return json.loads(self.canonical_json)


@dataclass(frozen=True)
class ReplayTransition:
    snapshot: FrozenSnapshot
    action_index: int
    action_id: str
    raw_cost_s: float
    reward: float
    mc_return: float
    terminated: bool
    next_snapshot: FrozenSnapshot | None

    def __post_init__(self) -> None:
        if not 0 <= self.action_index < len(self.snapshot.candidate_ids):
            raise ValueError("chosen index is outside the stored snapshot")
        if self.snapshot.candidate_ids[self.action_index] != self.action_id:
            raise ValueError("chosen candidate ID/index mismatch")
        if not self.snapshot.valid_mask[self.action_index]:
            raise ValueError("a selected replay action was invalid at sampling time")
        if self.terminated != (self.next_snapshot is None):
            raise ValueError("true terminal has no next snapshot; nonterminal must preserve one")


@dataclass(frozen=True)
class ReplayEpisode:
    transitions: tuple[ReplayTransition, ...]
    total_time_s: float
    tail_time_s: float
    prefix_time_s: float
    failed: bool
    true_source_count: int  # Trainer metadata only: never included in thawed snapshots.
    episode_id: str = ""


def build_replay_episode(
    decisions: Sequence[Mapping[str, Any]], *, tail_time_s: float,
    true_source_count: int, failed: bool, total_time_s: float | None = None,
    prefix_time_s: float = 0.0, episode_id: str = "",
) -> ReplayEpisode:
    """Fold a complete deterministic tail into the last learned transition.

    This constructor only accepts complete episodes. Artificial sampler pauses must
    be resumed first. Empty-decision fallback episodes have no synthetic Q/PPO action.
    Prefix costs before any policy choice are explicit ledger data, not past-action Q costs.
    """
    if isinstance(tail_time_s, bool) or isinstance(prefix_time_s, bool):
        raise ValueError("prefix and tail costs cannot be booleans")
    tail = float(tail_time_s)
    prefix = float(prefix_time_s)
    if not all(math.isfinite(x) and x >= 0 for x in (tail, prefix)):
        raise ValueError("prefix and fallback tail costs must be finite and nonnegative")
    if any(isinstance(d["delta_time_s"], bool) for d in decisions):
        raise ValueError("actual macro cost cannot be boolean")
    raw_costs = [float(d["delta_time_s"]) for d in decisions]
    # Validate even for empty episodes; also rules out invalid source counts and costs.
    normalized_rewards(raw_costs, true_source_count, failed=failed)
    ledger_total = math.fsum(raw_costs) + tail + prefix
    if isinstance(total_time_s, bool):
        raise ValueError("whole-episode time cannot be boolean")
    total = ledger_total if total_time_s is None else float(total_time_s)
    if not math.isfinite(total) or abs(total - ledger_total) > 1e-5:
        raise ValueError(f"macro + prefix + tail ledger mismatch: {ledger_total} != {total}")
    costs = list(raw_costs)
    if costs:
        costs[-1] += tail
    rewards = normalized_rewards(costs, true_source_count, failed=failed)
    returns = undiscounted_returns(rewards)
    snapshots = [FrozenSnapshot.capture(d["snapshot"]) for d in decisions]
    transitions = []
    for i, decision in enumerate(decisions):
        index = decision["index"]
        if isinstance(index, bool) or not isinstance(index, int):
            raise ValueError("decision index must be an integer")
        snap = snapshots[i]
        if not 0 <= index < len(snap.candidate_ids):
            raise ValueError("decision index is outside candidate snapshot")
        chosen_id = decision.get("candidate_id", snap.candidate_ids[index])
        terminated = i == len(decisions) - 1
        transitions.append(ReplayTransition(
            snap, index, chosen_id, costs[i], rewards[i], returns[i], terminated,
            None if terminated else snapshots[i + 1],
        ))
    return ReplayEpisode(tuple(transitions), total, tail, prefix, failed, true_source_count, episode_id)


def replay_from_episode(raw: Mapping[str, Any], true_source_count: int, *,
                        success: bool | None = None, episode_id: str = "") -> ReplayEpisode:
    """Adapter for the core runner output; terminal truth is attached by the trainer."""
    if success is None:
        success = raw.get("success")
    if type(success) is not bool:
        raise ValueError("trainer must attach a true completed-episode success boolean")
    terminal = raw.get("terminal", raw.get("terminated"))
    if terminal in (False, None, "incomplete", "truncated", "paused"):
        raise ValueError("unfinished sampler output cannot enter complete-episode replay")
    if terminal not in (True, "success", "failure", "terminated", "deadline", "error"):
        raise ValueError(f"unknown terminal encoding: {terminal!r}")
    if terminal == "failure" and success:
        raise ValueError("inconsistent failure terminal with success label")
    total = raw.get("virtual_time_s", raw.get("total_time_s"))
    return build_replay_episode(
        raw["decisions"], tail_time_s=raw.get("tail_time_s", 0.0),
        prefix_time_s=raw.get("prefix_time_s", 0.0), true_source_count=true_source_count,
        failed=not success, total_time_s=total, episode_id=episode_id,
    )
