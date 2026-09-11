"""Shared-network BC and complete-episode Monte Carlo masked PPO.

No environment, source generator, or oracle is imported here. Selection accepts
only observable snapshots. Terminal N enters only PPO label construction.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import copy
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

import torch
from torch import nn

from shared import batch_snapshots
from .returns import complete_episode_returns


def freeze_snapshot(snapshot: Mapping[str, Any]) -> str:
    """Freeze the entire candidate payload, order, mask and feature snapshot."""
    return json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False)


def snapshot_hash(frozen: str) -> str:
    return hashlib.sha256(frozen.encode("utf-8")).hexdigest()


def _independent_cpu_copy(value: Any) -> Any:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().clone()
    if isinstance(value, dict):
        return {k: _independent_cpu_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_independent_cpu_copy(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_independent_cpu_copy(v) for v in value)
    return copy.deepcopy(value)


def masked_log_probs(logits: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    if logits.ndim != 2 or mask.shape != logits.shape or mask.dtype != torch.bool:
        raise ValueError("logits and bool mask must have identical [batch, candidate] shape")
    if not bool(mask.any(dim=1).all()):
        raise ValueError("every decision needs at least one valid action")
    if not bool(torch.isfinite(logits[mask]).all()):
        raise ValueError("valid action logits must be finite")
    return torch.log_softmax(logits.masked_fill(~mask, -torch.inf), dim=-1)


@dataclass(frozen=True)
class Choice:
    index: int
    old_logprob: float
    old_value: float
    policy_version: int
    snapshot_json: str
    sampled: bool
    algorithm: str

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm, "sampled": self.sampled,
            "old_logprob": self.old_logprob, "old_value": self.old_value,
            "policy_version": self.policy_version,
            "snapshot_sha256": snapshot_hash(self.snapshot_json),
        }

    def as_core_choice(self) -> dict[str, Any]:
        # Core itself retains a detached full snapshot. The digest detects any
        # change instead of silently recomputing ratios on altered candidates.
        return {"index": self.index, "metadata": self.metadata}


@dataclass(frozen=True)
class PPOConfig:
    learning_rate: float = 3e-4
    clip_epsilon: float = 0.2
    epochs: int = 4
    max_grad_norm: float = 0.5
    value_coefficient: float = 0.5
    forward_batch_size: int = 128
    t0: float = 1000.0
    failure_penalty: float = 100.0


@dataclass(frozen=True)
class BCConfig:
    learning_rate: float = 3e-4
    epochs: int = 4
    max_grad_norm: float = 0.5
    forward_batch_size: int = 128


@dataclass(frozen=True)
class PPORow:
    snapshot_json: str
    action: int
    old_logprob: float
    old_value: float
    return_label: float
    policy_version: int


@dataclass(frozen=True)
class PPOEpisode:
    """Training rows only; forced actions contribute cost without logprob rows."""

    rows: tuple[PPORow, ...]
    cost_from_first_decision_s: float
    terminal: str


def _terminal(raw: Mapping[str, Any]) -> str:
    terminal = raw.get("terminal")
    if terminal in ("incomplete", "truncated", "paused", False, None):
        raise ValueError("artificial/incomplete episode cannot be used in PPO")
    if terminal not in (True, "success", "failure", "terminated", "deadline", "error"):
        raise ValueError(f"unknown terminal encoding: {terminal!r}")
    success = raw.get("success")
    if type(success) is not bool:
        raise ValueError("complete episode requires a bool success label")
    if terminal == "failure" and success:
        raise ValueError("inconsistent failure terminal and success label")
    if terminal == "success" and not success:
        # A validator can invalidate an apparently successful exit. Its final
        # success=False converts it to a real failed episode, not a truncation.
        return "failure"
    return "success" if success else "failure"


def _checked_action(snapshot: Mapping[str, Any], action: Any) -> int:
    if isinstance(action, bool) or not isinstance(action, int):
        raise ValueError("action index must be an integer")
    mask = snapshot["valid_mask"]
    if not 0 <= action < len(mask) or type(mask[action]) is not bool or not mask[action]:
        raise ValueError("recorded action must be valid in its original mask")
    return action


def episode_from_core(raw: Mapping[str, Any], *, true_n: int) -> PPOEpisode:
    """Build training labels from root-validated core output plus terminal N.

    Prefix costs occur before the first selector decision and cannot be changed
    by any later policy choice. They remain in root's whole-episode ledger but
    are not inserted into future returns. Macro deltas and tail are disjoint.
    """
    terminal = _terminal(raw)
    decisions = raw.get("decisions", ())
    labels = complete_episode_returns(
        [d["delta_time_s"] for d in decisions],
        tail_time_s=raw.get("tail_time_s", 0.0), true_n=true_n,
        terminal=terminal,
    )
    rows = []
    for decision, return_label in zip(decisions, labels.returns):
        metadata = decision.get("metadata") or {}
        if metadata.get("algorithm") != "ppo" or metadata.get("sampled") is not True:
            # Such actions affect earlier returns, but were not sampled by the
            # trainable policy and therefore have no score-function term.
            continue
        frozen = freeze_snapshot(decision["snapshot"])
        if metadata.get("snapshot_sha256") != snapshot_hash(frozen):
            raise ValueError("snapshot changed after sampling; PPO ratio is invalid")
        action = _checked_action(decision["snapshot"], decision["index"])
        old_logprob = float(metadata["old_logprob"])
        old_value = float(metadata["old_value"])
        version = metadata["policy_version"]
        if not math.isfinite(old_logprob) or old_logprob > 1e-6:
            raise ValueError("old log probability must be finite and <= 0")
        if not math.isfinite(old_value):
            raise ValueError("old value must be finite")
        if type(version) is not int or version < 0:
            raise ValueError("policy_version must be a nonnegative integer")
        rows.append(PPORow(frozen, action, old_logprob, old_value,
                           return_label, version))
    return PPOEpisode(tuple(rows), labels.accounted_cost_s, terminal)


def clipped_episode_losses(
    new_logprobs: torch.Tensor, old_logprobs: torch.Tensor,
    values: torch.Tensor, returns: torch.Tensor, old_values: torch.Tensor,
    episode_ids: torch.Tensor, *, episode_count: int, clip_epsilon: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Auditable full-batch loss, including empty episodes in the denominator."""
    if episode_count < 1:
        raise ValueError("episode_count must be positive")
    if any(t.shape != new_logprobs.shape for t in
           (old_logprobs, values, returns, old_values, episode_ids)):
        raise ValueError("all row vectors must have identical shapes")
    if new_logprobs.ndim != 1:
        raise ValueError("loss inputs must be vectors")
    if episode_ids.dtype != torch.long:
        raise ValueError("episode_ids must be int64")
    if episode_ids.numel() and (int(episode_ids.min()) < 0 or
                               int(episode_ids.max()) >= episode_count):
        raise ValueError("episode id outside batch")
    advantages = (returns - old_values).detach()
    ratio = torch.exp(new_logprobs - old_logprobs.detach())
    surrogate = torch.minimum(ratio * advantages,
                              ratio.clamp(1-clip_epsilon, 1+clip_epsilon) * advantages)
    actor_loss = -surrogate.sum() / episode_count
    counts = torch.bincount(episode_ids, minlength=episode_count).clamp_min(1)
    weights = 1 / (episode_count * counts[episode_ids].to(values.dtype))
    value_loss = ((values - returns.detach()).square() * weights).sum()
    return actor_loss, value_loss


class _Selector:
    def __init__(self, model: nn.Module, *, device: str | torch.device = "cpu", seed: int = 0):
        self.device = torch.device(device)
        self.model = model.to(self.device)
        self.policy_version = 0
        self.generator = torch.Generator(device="cpu").manual_seed(seed)

    def state_dict(self) -> dict[str, Any]:
        """Root owns persistence; include optimizer, sampling RNG and policy version."""
        return _independent_cpu_copy({
            "model": self.model.state_dict(), "optimizer": self.optimizer.state_dict(),
            "policy_version": self.policy_version,
            "sampling_rng": self.generator.get_state(),
            "config": asdict(self.config), "trainer": type(self).__name__})

    def load_state_dict(self, state: Mapping[str, Any]) -> None:
        if state["trainer"] != type(self).__name__ or state["config"] != asdict(self.config):
            raise ValueError("checkpoint trainer/configuration mismatch")
        self.model.load_state_dict(state["model"], strict=True)
        self.optimizer.load_state_dict(state["optimizer"])
        self.policy_version = int(state["policy_version"])
        self.generator.set_state(state["sampling_rng"].cpu())

    def _select(self, snapshot: Mapping[str, Any], *, stochastic: bool,
                algorithm: str) -> Choice:
        frozen = freeze_snapshot(snapshot)
        retained = json.loads(frozen)
        self.model.eval()
        with torch.no_grad():
            batch = batch_snapshots([retained], device=self.device)
            logits, values = self.model(**batch)
            log_probs = masked_log_probs(logits, batch["mask"])
            if stochastic:
                # CPU RNG also works when the network runs on MPS. This copy is
                # included in actual selector latency, not hidden in a benchmark.
                probs = log_probs[0].exp().cpu()
                action = int(torch.multinomial(probs, 1, generator=self.generator).item())
            else:
                action = int(log_probs[0].argmax().item())
            value = float(values.reshape(-1)[0].item())
            if not math.isfinite(value):
                raise ValueError("critic value must be finite")
            return Choice(action, float(log_probs[0, action].item()), value,
                          self.policy_version, frozen, stochastic, algorithm)


class PPOTrainer(_Selector):
    def __init__(self, model: nn.Module, config: PPOConfig | None = None,
                 *, device: str | torch.device = "cpu", seed: int = 0):
        super().__init__(model, device=device, seed=seed)
        self.config = config or PPOConfig()
        c = self.config
        if c.t0 != 1000.0 or c.failure_penalty != 100.0:
            raise ValueError("common task units are fixed at T0=1000, penalty=100")
        if not (0 < c.clip_epsilon < 1 and c.epochs >= 1 and
                c.forward_batch_size >= 1 and c.max_grad_norm > 0):
            raise ValueError("invalid PPO configuration")
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=c.learning_rate)

    def select(self, snapshot: Mapping[str, Any], *, deterministic: bool = False) -> Choice:
        return self._select(snapshot, stochastic=not deterministic, algorithm="ppo")

    def update(self, episodes: Sequence[PPOEpisode]) -> dict[str, float | int]:
        if not episodes:
            raise ValueError("PPO needs a nonempty complete-episode batch")
        flat = [(row, len(ep.rows)) for ep in episodes for row in ep.rows]
        if not flat:
            return {"episodes": len(episodes), "decisions": 0, "optimizer_steps": 0,
                    "policy_version": self.policy_version}
        if any(row.policy_version != self.policy_version for row, _ in flat):
            raise ValueError("off-policy or stale rollout version; collect current-policy episodes")
        # Return labels and old values were fixed before the first PPO epoch.
        c, b = self.config, len(episodes)
        metrics = {"actor_loss": 0.0, "value_loss": 0.0, "approx_kl": 0.0,
                   "clip_fraction": 0.0, "gradient_norm": 0.0}
        self.model.train()
        for epoch in range(c.epochs):
            self.optimizer.zero_grad(set_to_none=True)
            for offset in range(0, len(flat), c.forward_batch_size):
                chunk = flat[offset:offset+c.forward_batch_size]
                rows, lengths = zip(*chunk)
                batch = batch_snapshots([json.loads(r.snapshot_json) for r in rows],
                                        device=self.device)
                logits, values = self.model(**batch)
                log_probs = masked_log_probs(logits, batch["mask"])
                actions = torch.tensor([r.action for r in rows], device=self.device)
                new = log_probs.gather(1, actions[:, None]).squeeze(1)
                old = new.new_tensor([r.old_logprob for r in rows])
                returns = new.new_tensor([r.return_label for r in rows])
                old_values = new.new_tensor([r.old_value for r in rows])
                if epoch == 0:
                    # Version counters alone cannot distinguish two separately
                    # initialized trainers. Verify behavior before the first
                    # optimizer step, using this already-required forward pass.
                    same_logprob = torch.isclose(new.detach(), old, atol=2e-4, rtol=1e-5)
                    same_value = torch.isclose(values.detach().reshape(-1), old_values,
                                               atol=2e-4, rtol=1e-5)
                    if not bool(same_logprob.all() and same_value.all()):
                        self.optimizer.zero_grad(set_to_none=True)
                        raise ValueError("recorded old policy/value differ from current model")
                advantage = (returns - old_values).detach()
                ratio = (new-old).exp()
                surrogate = torch.minimum(ratio*advantage,
                    ratio.clamp(1-c.clip_epsilon, 1+c.clip_epsilon)*advantage)
                actor_loss = -surrogate.sum() / b
                value_weights = new.new_tensor([1/(b*n) for n in lengths])
                value_loss = ((values.reshape(-1)-returns).square()*value_weights).sum()
                loss = actor_loss+c.value_coefficient*value_loss
                if not bool(torch.isfinite(loss)):
                    self.optimizer.zero_grad(set_to_none=True)
                    raise FloatingPointError("nonfinite PPO loss; no optimizer step performed")
                loss.backward()
                metrics["actor_loss"] += float(actor_loss.detach())/c.epochs
                metrics["value_loss"] += float(value_loss.detach())/c.epochs
                with torch.no_grad():
                    logratio = new-old
                    metrics["approx_kl"] += float((ratio-1-logratio).sum())/(len(flat)*c.epochs)
                    metrics["clip_fraction"] += float(((ratio-1).abs()>c.clip_epsilon).sum())/(len(flat)*c.epochs)
            norm = nn.utils.clip_grad_norm_(self.model.parameters(), c.max_grad_norm,
                                            error_if_nonfinite=True)
            metrics["gradient_norm"] += float(norm)/c.epochs
            self.optimizer.step()
        self.policy_version += 1
        return {**metrics, "episodes": b, "decisions": len(flat),
                "optimizer_steps": c.epochs, "policy_version": self.policy_version}


class BCTrainer(_Selector):
    """Episode-equal mean cross entropy on shared C7 demonstrations."""

    def __init__(self, model: nn.Module, config: BCConfig | None = None,
                 *, device: str | torch.device = "cpu", seed: int = 0):
        super().__init__(model, device=device, seed=seed)
        self.config = config or BCConfig()
        c = self.config
        if c.epochs < 1 or c.forward_batch_size < 1 or c.max_grad_norm <= 0:
            raise ValueError("invalid BC configuration")
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=c.learning_rate)

    def select(self, snapshot: Mapping[str, Any], *, deterministic: bool = True) -> Choice:
        return self._select(snapshot, stochastic=not deterministic, algorithm="bc")

    def update(self, episodes: Sequence[Mapping[str, Any]]) -> dict[str, float | int]:
        if not episodes:
            raise ValueError("BC needs a nonempty episode batch")
        flat = []
        for episode in episodes:
            _terminal(episode)
            decisions = episode.get("decisions", ())
            for decision in decisions:
                frozen = freeze_snapshot(decision["snapshot"])
                snapshot = json.loads(frozen)
                action = _checked_action(snapshot, decision["index"])
                if action != snapshot["teacher_index"]:
                    raise ValueError("shared pure-C7 demonstration must use its teacher action")
                flat.append((frozen, action, len(decisions)))
        if not flat:
            return {"episodes": len(episodes), "decisions": 0, "optimizer_steps": 0,
                    "policy_version": self.policy_version}
        c, b = self.config, len(episodes)
        total_loss = 0.0
        self.model.train()
        for _ in range(c.epochs):
            self.optimizer.zero_grad(set_to_none=True)
            for offset in range(0, len(flat), c.forward_batch_size):
                rows = flat[offset:offset+c.forward_batch_size]
                batch = batch_snapshots([json.loads(r[0]) for r in rows], device=self.device)
                logits, _ = self.model(**batch)
                log_probs = masked_log_probs(logits, batch["mask"])
                actions = torch.tensor([r[1] for r in rows], device=self.device)
                selected = log_probs.gather(1, actions[:, None]).squeeze(1)
                weights = selected.new_tensor([1/(b*r[2]) for r in rows])
                loss = -(selected*weights).sum()
                if not bool(torch.isfinite(loss)):
                    self.optimizer.zero_grad(set_to_none=True)
                    raise FloatingPointError("nonfinite BC loss; no optimizer step performed")
                loss.backward()
                total_loss += float(loss.detach())/c.epochs
            nn.utils.clip_grad_norm_(self.model.parameters(), c.max_grad_norm,
                                     error_if_nonfinite=True)
            self.optimizer.step()
        self.policy_version += 1
        return {"cross_entropy": total_loss, "episodes": b, "decisions": len(flat),
                "optimizer_steps": c.epochs, "policy_version": self.policy_version}
