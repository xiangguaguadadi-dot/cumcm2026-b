"""D3's 61,121-parameter public-feature scorer; no data or environment access.

``CounterfactualModel(features)`` returns raw f_theta scores, not probabilities
or a policy decision. The caller computes differences to its retained teacher,
applies its independently frozen calibration threshold, and resolves ID ties.

Inputs are exactly the six tensor keys below. A single state returns ``[K]``;
adding a common batch dimension returns ``[B, K]``. Batches must have the same
K: action padding is deliberately unsupported. Event padding uses a boolean
mask, with at least one real event per state. Metadata, labels, candidate IDs,
and ``events_dropped`` belong outside this numerical interface.
"""
from __future__ import annotations

from collections.abc import Mapping

import torch
from torch import Tensor, nn


EXPECTED_PARAMETER_COUNT = 61_121
FEATURE_KEYS = frozenset((
    'global_features', 'channels', 'active_events', 'active_mask',
    'polygon', 'actions',
))


def _two_layer_encoder(input_width: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Linear(input_width, 32), nn.ReLU(),
        nn.Linear(32, 32), nn.ReLU(),
    )


class _SetEncoder(nn.Module):
    """Shared element encoder, mean/max pooling, then a 64-to-64 MLP."""

    def __init__(self, input_width: int):
        super().__init__()
        self.elements = _two_layer_encoder(input_width)
        self.pooled = nn.Sequential(nn.Linear(64, 64), nn.ReLU())

    def forward(self, values: Tensor, mask: Tensor | None = None) -> Tensor:
        if mask is None:
            hidden = self.elements(values)
            mean = hidden.mean(dim=1)
            maximum = hidden.amax(dim=1)
        else:
            present = mask.unsqueeze(-1)
            # Zero before the MLP as well: arbitrary finite padding must not
            # overflow a hidden layer or contribute through its biases.
            hidden = self.elements(values.masked_fill(~present, 0.))
            mean = hidden.masked_fill(~present, 0.).sum(dim=1)
            mean = mean / mask.sum(dim=1, keepdim=True).to(hidden.dtype)
            maximum = hidden.masked_fill(
                ~present, torch.finfo(hidden.dtype).min,
            ).amax(dim=1)
        return self.pooled(torch.cat((mean, maximum), dim=-1))


class CounterfactualModel(nn.Module):
    """Public tensors -> one unrestricted scalar f_theta for each action."""

    def __init__(self):
        super().__init__()
        self.event_encoder = _SetEncoder(14)
        self.polygon_encoder = _SetEncoder(2)
        self.channel_encoder = _SetEncoder(12)
        self.global_encoder = _two_layer_encoder(20)
        self.action_encoder = _two_layer_encoder(14)
        self.head = nn.Sequential(
            nn.Linear(256, 128), nn.ReLU(),
            nn.Linear(128, 64), nn.ReLU(),
            nn.Linear(64, 1),
        )
        actual = sum(parameter.numel() for parameter in self.parameters())
        if actual != EXPECTED_PARAMETER_COUNT:
            raise AssertionError(f'D3 parameter count changed: {actual}')

    def _checked_batch(self, features: Mapping[str, Tensor]) -> tuple[dict[str, Tensor], bool]:
        if not isinstance(features, Mapping):
            raise TypeError('Model inputs must be a mapping of public tensors')
        if set(features) != FEATURE_KEYS:
            raise ValueError('Model feature keys must match the six-field whitelist')
        if any(not isinstance(value, Tensor) for value in features.values()):
            raise TypeError('All six model inputs must be torch.Tensor objects')

        global_values = features['global_features']
        if global_values.ndim not in (1, 2):
            raise ValueError('global_features must have shape [20] or [B, 20]')
        single = global_values.ndim == 1
        batch = {key: value.unsqueeze(0) if single else value
                 for key, value in features.items()}
        dimensions = {
            'global_features': 2, 'channels': 3, 'active_events': 3,
            'active_mask': 2, 'polygon': 3, 'actions': 3,
        }
        if any(batch[key].ndim != rank for key, rank in dimensions.items()):
            raise ValueError('Mixed single/batch ranks or invalid feature dimensions')

        batch_size = batch['global_features'].shape[0]
        event_count = batch['active_events'].shape[1]
        action_count = batch['actions'].shape[1]
        if batch_size < 1 or not 1 <= event_count <= 128 or not 1 <= action_count <= 9:
            raise ValueError('Require B >= 1, 1 <= L <= 128 and 1 <= K <= 9')
        shapes = {
            'global_features': (batch_size, 20),
            'channels': (batch_size, 20, 12),
            'active_events': (batch_size, event_count, 14),
            'active_mask': (batch_size, event_count),
            'polygon': (batch_size, 32, 2),
            'actions': (batch_size, action_count, 14),
        }
        if any(tuple(batch[key].shape) != shape for key, shape in shapes.items()):
            raise ValueError('Feature shape does not match the D2 tensor contract')

        parameter = self.head[0].weight
        for key, value in batch.items():
            if value.device != parameter.device:
                raise ValueError(f'{key} device must match the model')
            if key == 'active_mask':
                if value.dtype != torch.bool:
                    raise TypeError('active_mask must have boolean dtype')
            else:
                if not value.is_floating_point() or value.dtype != parameter.dtype:
                    raise TypeError(f'{key} floating dtype must match the model')
                if not torch.isfinite(value).all().item():
                    raise ValueError(f'{key} contains a nonfinite value')
        if not batch['active_mask'].any(dim=1).all().item():
            raise ValueError('Every state requires at least one unmasked public event')
        return batch, single

    def forward(self, features: Mapping[str, Tensor]) -> Tensor:
        batch, single = self._checked_batch(features)
        shared = torch.cat((
            self.event_encoder(batch['active_events'], batch['active_mask']),
            self.polygon_encoder(batch['polygon']),
            self.channel_encoder(batch['channels']),
            self.global_encoder(batch['global_features']),
        ), dim=-1)
        actions = self.action_encoder(batch['actions'])
        expanded = shared.unsqueeze(1).expand(-1, actions.shape[1], -1)
        scores = self.head(torch.cat((expanded, actions), dim=-1)).squeeze(-1)
        if not torch.isfinite(scores).all().item():
            raise ValueError('Model produced nonfinite action scores')
        return scores[0] if single else scores
