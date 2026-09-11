"""Small permutation-equivariant candidate network shared by PPO, BC and Q.

Only explicit observable feature arrays enter tensors. Teacher labels, payloads,
episode metadata, source truth and normalized training rewards are excluded.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
import math
import torch
from torch import nn

NETWORK_VERSION = 'candidate-shared-attention-v1'
GLOBAL_DIM, CANDIDATE_DIM, CHANNEL_DIM = 16, 16, 12


def batch_snapshots(snapshots: Sequence[Mapping], device='cpu') -> dict[str, torch.Tensor]:
    if not snapshots:
        raise ValueError('at least one snapshot is required')
    count = len(snapshots)
    lengths = [len(s['candidate_features']) for s in snapshots]
    if min(lengths) < 1 or max(lengths) > 64:
        raise ValueError('candidate count must be in 1..64')
    width = max(lengths)
    glob = torch.empty((count, GLOBAL_DIM), dtype=torch.float32)
    channels = torch.empty((count, 20, CHANNEL_DIM), dtype=torch.float32)
    candidates = torch.zeros((count, width, CANDIDATE_DIM), dtype=torch.float32)
    mask = torch.zeros((count, width), dtype=torch.bool)
    for i, (snap, n) in enumerate(zip(snapshots, lengths)):
        # Deliberately do not traverse or copy any other snapshot field.
        g = torch.as_tensor(snap['global_features'], dtype=torch.float32)
        c = torch.as_tensor(snap['channel_features'], dtype=torch.float32)
        a = torch.as_tensor(snap['candidate_features'], dtype=torch.float32)
        if not all(type(value) is bool for value in snap['valid_mask']):
            raise ValueError('valid_mask entries must be explicit booleans')
        m = torch.as_tensor(snap['valid_mask'], dtype=torch.bool)
        if g.shape != (GLOBAL_DIM,) or c.shape != (20, CHANNEL_DIM) or a.shape != (n, CANDIDATE_DIM) or m.shape != (n,):
            raise ValueError('snapshot feature shape does not match shared schema')
        if not bool(m.any()):
            raise ValueError('no valid candidate; controller must take over')
        if not all(bool(torch.isfinite(x).all()) for x in (g,c,a)):
            raise ValueError('non-finite observable feature')
        glob[i], channels[i], candidates[i,:n], mask[i,:n] = g,c,a,m
    return dict(global_features=glob.to(device), candidate_features=candidates.to(device),
                mask=mask.to(device), channel_features=channels.to(device))


class CandidateNetwork(nn.Module):
    """One common backbone, candidate scores and an observable state value.

    Candidate scores act as logits for PPO/BC or normalized Q values for Q.
    The extra state-value head is unused by Q; its size is reported separately.
    No position embeddings, candidate-index features, graph kernels or GRU.
    """
    def __init__(self, global_dim=GLOBAL_DIM, candidate_dim=CANDIDATE_DIM,
                 channel_dim=CHANNEL_DIM, hidden_dim=64):
        super().__init__()
        self.config = dict(global_dim=global_dim, candidate_dim=candidate_dim,
                           channel_dim=channel_dim, hidden_dim=hidden_dim)
        h = hidden_dim
        self.global_encoder = nn.Sequential(nn.Linear(global_dim,h),nn.SiLU())
        self.channel_encoder = nn.Sequential(nn.Linear(channel_dim,h),nn.SiLU())
        self.candidate_encoder = nn.Sequential(nn.Linear(candidate_dim,h),nn.SiLU())
        self.query = nn.Linear(h,h,bias=False)
        self.key = nn.Linear(h,h,bias=False)
        self.score_head = nn.Sequential(nn.Linear(3*h,h),nn.SiLU(),nn.Linear(h,1))
        self.value_head = nn.Sequential(nn.Linear(2*h,h),nn.SiLU(),nn.Linear(h,1))
        self._scale = math.sqrt(h)

    def forward(self, global_features, candidate_features, mask, channel_features=None):
        if channel_features is None:
            raise ValueError('all models require the shared observable channel features')
        if mask.dtype != torch.bool or mask.ndim != 2 or not bool(mask.any(dim=1).all()):
            raise ValueError('each batch item requires a boolean mask and valid action')
        g = self.global_encoder(global_features)
        c = self.channel_encoder(channel_features)
        a = self.candidate_encoder(candidate_features)
        weights = torch.softmax(torch.matmul(self.query(a),self.key(c).transpose(-1,-2))/self._scale, dim=-1)
        context = torch.matmul(weights,c)
        joined = torch.cat((a,context,g[:,None,:].expand(-1,a.shape[1],-1)),dim=-1)
        scores = self.score_head(joined).squeeze(-1).masked_fill(~mask,float('-inf'))
        values = self.value_head(torch.cat((g,c.mean(dim=1)),dim=-1)).squeeze(-1)
        return scores, values

    def architecture_record(self):
        total = sum(p.numel() for p in self.parameters())
        value = sum(p.numel() for p in self.value_head.parameters())
        return dict(version=NETWORK_VERSION,config=self.config,total_parameters=total,
                    state_value_head_parameters=value,candidate_path_parameters=total-value)
