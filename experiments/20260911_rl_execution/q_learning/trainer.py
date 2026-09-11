"""Shared-network MC regression and normalized, behavior-supported Double-Q updates."""
from __future__ import annotations

import copy
import random
from collections.abc import Sequence

import torch
from shared import CandidateNetwork, batch_snapshots

from .policy import FeatureBounds, QSelector, TrainingExplorer, choose_q_action, FEATURE_RANGE_CONTRACT
from .replay import ReplayEpisode, ReplayTransition


class QTrainer:
    def __init__(self, network: CandidateNetwork, support_model: CandidateNetwork, *,
                 device="cpu", learning_rate=3e-4, kappa=0.1, target_tau=0.01,
                 max_grad_norm=0.5, microbatch_size=128,
                 feature_bounds: FeatureBounds | None = None):
        if not 0 <= kappa <= 1 or not 0 < target_tau <= 1:
            raise ValueError("invalid behavior gate or target update coefficient")
        if microbatch_size < 1:
            raise ValueError("microbatch_size must be positive")
        self.device = device
        self.network = network.to(device)
        self.target = copy.deepcopy(network).to(device).eval().requires_grad_(False)
        self.support_model = copy.deepcopy(support_model).to(device).eval().requires_grad_(False)
        self.optimizer = torch.optim.Adam(self.network.parameters(), lr=learning_rate)
        self.kappa = float(kappa)
        self.target_tau = float(target_tau)
        self.max_grad_norm = float(max_grad_norm)
        self.microbatch_size = int(microbatch_size)
        self.feature_bounds = feature_bounds
        self.update_count = 0
        self._selectors = []
        self.feature_range_history = []

    def _next_values(self, transitions: Sequence[ReplayTransition]) -> torch.Tensor:
        result = torch.zeros(len(transitions), dtype=torch.float32, device=self.device)
        indices = [i for i, t in enumerate(transitions) if not t.terminated]
        if not indices:
            return result
        snapshots = [transitions[i].next_snapshot.thaw() for i in indices]
        batch = batch_snapshots(snapshots, self.device)
        with torch.no_grad():
            online, _ = self.network(**batch)
            target, _ = self.target(**batch)
            behavior, _ = self.support_model(**batch)
            choices = []
            for row, snap in enumerate(snapshots):
                n = len(snap["candidate_ids"])
                decision = choose_q_action(snap, online[row, :n].detach().cpu().tolist(),
                                           behavior[row, :n].detach().cpu().tolist(),
                                           kappa=self.kappa, feature_bounds=self.feature_bounds)
                choices.append(decision["index"])
            chosen = torch.tensor(choices, dtype=torch.long, device=self.device)
            # Same deployment guard and saved ordering; target network only evaluates that action.
            values = target.gather(1, chosen[:, None]).squeeze(1)
            if not bool(torch.isfinite(values).all()):
                raise FloatingPointError("nonfinite target value for deployed next action")
            result[torch.tensor(indices, dtype=torch.long, device=self.device)] = values
        return result

    def targets(self, transitions: Sequence[ReplayTransition], *, kind="td") -> torch.Tensor:
        if kind == "mc":
            return torch.tensor([t.mc_return for t in transitions], dtype=torch.float32, device=self.device)
        if kind != "td":
            raise ValueError("kind must be mc or td")
        rewards = torch.tensor([t.reward for t in transitions], dtype=torch.float32, device=self.device)
        # Terminal rows never materialize, inspect or bootstrap a next snapshot.
        return rewards + self._next_values(transitions)

    def update(self, episodes: Sequence[ReplayEpisode], *, kind="td") -> dict:
        if not episodes:
            raise ValueError("uniform episode batch cannot be empty")
        transitions = [t for ep in episodes for t in ep.transitions]
        if not transitions:
            return {"kind": kind, "episodes": len(episodes), "transitions": 0,
                    "loss": 0.0, "optimizer_step": False, "update_count": self.update_count}
        self.network.train()
        self.target.eval()
        self.support_model.eval()
        self.optimizer.zero_grad(set_to_none=True)
        loss_total, absolute_targets = 0.0, 0.0
        for start in range(0, len(transitions), self.microbatch_size):
            chunk = transitions[start:start + self.microbatch_size]
            snapshots = [t.snapshot.thaw() for t in chunk]
            batch = batch_snapshots(snapshots, self.device)
            scores, _ = self.network(**batch)
            actions = torch.tensor([t.action_index for t in chunk], dtype=torch.long, device=self.device)
            selected = scores.gather(1, actions[:, None]).squeeze(1)
            labels = self.targets(chunk, kind=kind).detach()
            if not bool(torch.isfinite(selected).all() and torch.isfinite(labels).all()):
                raise FloatingPointError("nonfinite selected Q or label")
            # Equal episodes, sum their transition residuals. Microbatches do not change this weight.
            loss = ((selected - labels) ** 2).sum() / len(episodes)
            if not bool(torch.isfinite(loss)):
                self.optimizer.zero_grad(set_to_none=True)
                raise FloatingPointError("nonfinite Q loss; no optimizer step performed")
            loss.backward()
            loss_total += float(loss.detach().cpu())
            absolute_targets += float(labels.abs().sum().cpu())
        grad_norm = torch.nn.utils.clip_grad_norm_(self.network.parameters(), self.max_grad_norm,
                                                  error_if_nonfinite=True)
        self.optimizer.step()
        with torch.no_grad():
            for dst, src in zip(self.target.parameters(), self.network.parameters()):
                dst.lerp_(src, self.target_tau)
        self.update_count += 1
        return {"kind": kind, "episodes": len(episodes), "transitions": len(transitions),
                "loss": loss_total, "mean_absolute_target": absolute_targets / len(transitions),
                "gradient_norm_before_clip": float(grad_norm.detach().cpu()),
                "optimizer_step": True, "update_count": self.update_count}

    def fit(self, episodes: Sequence[ReplayEpisode], *, kind="td", epochs=1,
            batch_episodes=8, seed=0) -> list[dict]:
        if epochs < 0 or batch_episodes < 1:
            raise ValueError("epochs and batch_episodes must be valid")
        rng = random.Random(seed)
        history = []
        for epoch in range(epochs):
            order = list(range(len(episodes)))
            rng.shuffle(order)
            for start in range(0, len(order), batch_episodes):
                selected = [episodes[i] for i in order[start:start + batch_episodes]]
                metrics = self.update(selected, kind=kind)
                metrics["epoch"] = epoch
                history.append(metrics)
        return history

    def sync_target(self):
        self.target.load_state_dict(self.network.state_dict())
        self.target.eval().requires_grad_(False)

    def fit_mc(self, episodes, **kwargs):
        history = self.fit(episodes, kind="mc", **kwargs)
        # TD begins from the completed MC initialization, not an old partial average.
        self.sync_target()
        return history

    def fit_td(self, episodes, **kwargs):
        return self.fit(episodes, kind="td", **kwargs)

    def register_training_snapshots(self, snapshots, *, source="q_training"):
        """Call only on newly executed shared C7 or this run's training observations.

        The runner owns split provenance. Selection/test observations must never be
        passed here. This is a predeclared cumulative range rule, not calibration.
        """
        if source not in ("shared_c7_demo", "q_training"):
            raise ValueError("feature ranges accept only registered demonstration or Q training data")
        rows = list(snapshots)
        if not rows:
            return {"added_snapshots": 0, "source": source}
        self.feature_bounds = (self.feature_bounds.extend(rows) if self.feature_bounds
                               else FeatureBounds.fit(rows))
        record = {"added_snapshots": len(rows), "source": source,
                  "revision": self.feature_bounds.revision, "gate_contract": FEATURE_RANGE_CONTRACT,
                  "cumulative_snapshots": self.feature_bounds.snapshot_count}
        self.feature_range_history.append(record)
        for selector in self._selectors:
            selector.feature_bounds = self.feature_bounds
        return dict(record)

    def make_selector(self, *, training=False, seed=0):
        selector = QSelector(self.network, self.support_model, device=self.device,
                             kappa=self.kappa, feature_bounds=self.feature_bounds,
                             enforce_bounds=True)
        self._selectors.append(selector)
        return TrainingExplorer(selector, seed=seed) if training else selector

    def checkpoint(self) -> dict:
        return {"format": "behavior-supported-q-v1", "network_config": dict(self.network.config),
                "network": {k: v.detach().cpu().clone() for k, v in self.network.state_dict().items()},
                "target": {k: v.detach().cpu().clone() for k, v in self.target.state_dict().items()},
                "support_model": {k: v.detach().cpu().clone() for k, v in self.support_model.state_dict().items()},
                "optimizer": copy.deepcopy(self.optimizer.state_dict()), "kappa": self.kappa,
                "architecture": self.network.architecture_record(),
                "unused_q_head": "state_value_head (reported by common architecture_record)",
                "target_tau": self.target_tau, "max_grad_norm": self.max_grad_norm,
                "microbatch_size": self.microbatch_size, "update_count": self.update_count,
                "feature_bounds": self.feature_bounds.to_dict() if self.feature_bounds else None,
                "feature_range_history": copy.deepcopy(self.feature_range_history),
                "feature_range_contract": FEATURE_RANGE_CONTRACT,
                "next_action_contract": "deployment_bounds_teacher_supported_argmax_v2_clock_physical",
                "label_contract": {"T0": 1000.0, "gamma": 1.0, "failure_penalty_once": 100.0,
                                   "true_N_is_deployment_input": False}}

    @classmethod
    def from_checkpoint(cls, checkpoint: dict, *, device="cpu"):
        if checkpoint["format"] != "behavior-supported-q-v1":
            raise ValueError("unexpected Q checkpoint format")
        if checkpoint.get("feature_range_contract") != FEATURE_RANGE_CONTRACT:
            raise ValueError("checkpoint clock/range gate contract differs")
        expected = {"T0": 1000.0, "gamma": 1.0, "failure_penalty_once": 100.0,
                    "true_N_is_deployment_input": False}
        if checkpoint.get("label_contract") != expected:
            raise ValueError("checkpoint reward units or privileged-input contract differ")
        network = CandidateNetwork(**checkpoint["network_config"])
        support = CandidateNetwork(**checkpoint["network_config"])
        network.load_state_dict(checkpoint["network"])
        support.load_state_dict(checkpoint["support_model"])
        bounds = (FeatureBounds.from_dict(checkpoint["feature_bounds"])
                  if checkpoint.get("feature_bounds") else None)
        trainer = cls(network, support, device=device, kappa=checkpoint["kappa"],
                      target_tau=checkpoint["target_tau"], max_grad_norm=checkpoint["max_grad_norm"],
                      microbatch_size=checkpoint["microbatch_size"], feature_bounds=bounds)
        trainer.target.load_state_dict(checkpoint["target"])
        trainer.optimizer.load_state_dict(checkpoint["optimizer"])
        trainer.update_count = checkpoint["update_count"]
        if checkpoint.get("next_action_contract") != "deployment_bounds_teacher_supported_argmax_v2_clock_physical":
            raise ValueError("checkpoint next-action deployment contract differs")
        trainer.feature_range_history = copy.deepcopy(checkpoint.get("feature_range_history", []))
        return trainer
