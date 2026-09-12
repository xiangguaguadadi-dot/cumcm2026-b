"""Pure synthetic tensor/gradient checks: no dataset, optimizer or environment."""
from __future__ import annotations

import io
import unittest

import torch
from torch import nn

from ..model import CounterfactualModel, EXPECTED_PARAMETER_COUNT, FEATURE_KEYS


def synthetic_state(*, actions: int = 5, events: int = 4) -> dict[str, torch.Tensor]:
    return {
        'global_features': torch.randn(20),
        'channels': torch.randn(20, 12),
        'active_events': torch.randn(events, 14),
        'active_mask': torch.ones(events, dtype=torch.bool),
        'polygon': torch.randn(32, 2),
        'actions': torch.randn(actions, 14),
    }


def cloned(features):
    return {key: value.clone() for key, value in features.items()}


class ModelContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_threads = torch.get_num_threads()
        torch.set_num_threads(1)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.old_threads)

    def setUp(self):
        torch.manual_seed(912100)
        self.model = CounterfactualModel()
        self.features = synthetic_state()

    def test_exact_trainable_parameters_and_branch_sizes(self):
        expected = {'event_encoder': 5696, 'polygon_encoder': 5312,
                    'channel_encoder': 5632, 'global_encoder': 1728,
                    'action_encoder': 1536, 'head': 41217}
        self.assertEqual(sum(p.numel() for p in self.model.parameters() if p.requires_grad),
                         EXPECTED_PARAMETER_COUNT)
        self.assertEqual(EXPECTED_PARAMETER_COUNT, 61121)
        for name, count in expected.items():
            self.assertEqual(sum(p.numel() for p in getattr(self.model, name).parameters()), count)
        self.assertTrue(all(p.requires_grad for p in self.model.parameters()))
        self.assertEqual(sum(isinstance(x, nn.Linear) for x in self.model.modules()), 16)
        self.assertEqual(sum(isinstance(x, nn.ReLU) for x in self.model.modules()), 15)

    def test_single_state_returns_one_finite_score_per_action(self):
        scores = self.model(self.features)
        self.assertEqual(tuple(scores.shape), (5,))
        self.assertTrue(torch.isfinite(scores).all().item())
        self.assertEqual(set(self.features), FEATURE_KEYS)

    def test_single_action_and_maximum_registered_shapes(self):
        self.assertEqual(tuple(self.model(synthetic_state(actions=1, events=1)).shape), (1,))
        self.assertEqual(tuple(self.model(synthetic_state(actions=9, events=128)).shape), (9,))

    def test_batch_matches_independent_single_state_forwards(self):
        other = synthetic_state()
        batch = {key: torch.stack((self.features[key], other[key])) for key in FEATURE_KEYS}
        actual = self.model(batch)
        expected = torch.stack((self.model(self.features), self.model(other)))
        self.assertEqual(tuple(actual.shape), (2, 5))
        torch.testing.assert_close(actual, expected, rtol=1e-6, atol=1e-7)

    def test_batch_members_do_not_change_each_other(self):
        batch = {key: torch.stack((value, value.clone())) for key, value in self.features.items()}
        reference = self.model(batch)[0]
        for key in FEATURE_KEYS - {'active_mask'}:
            batch[key][1] += 100.
        torch.testing.assert_close(self.model(batch)[0], reference, rtol=0, atol=0)

    def test_channel_pooling_is_permutation_invariant(self):
        changed = cloned(self.features)
        changed['channels'] = changed['channels'][torch.randperm(20)]
        torch.testing.assert_close(self.model(changed), self.model(self.features), rtol=1e-6, atol=1e-7)

    def test_polygon_and_event_set_pooling_is_permutation_invariant(self):
        changed = cloned(self.features)
        changed['polygon'] = changed['polygon'][torch.randperm(32)]
        order = torch.randperm(4)
        changed['active_events'] = changed['active_events'][order]
        changed['active_mask'] = changed['active_mask'][order]
        torch.testing.assert_close(self.model(changed), self.model(self.features), rtol=1e-6, atol=1e-7)

    def test_action_scores_are_permutation_equivariant(self):
        order = torch.tensor([3, 1, 4, 0, 2])
        changed = cloned(self.features)
        changed['actions'] = changed['actions'][order]
        torch.testing.assert_close(self.model(changed), self.model(self.features)[order], rtol=1e-6, atol=1e-7)

    def test_padding_affects_neither_mean_nor_max(self):
        changed = cloned(self.features)
        changed['active_events'] = torch.cat((changed['active_events'], torch.full((5, 14), 1e30)))
        changed['active_mask'] = torch.cat((changed['active_mask'], torch.zeros(5, dtype=torch.bool)))
        torch.testing.assert_close(self.model(changed), self.model(self.features), rtol=1e-6, atol=1e-7)

    def test_masked_events_have_zero_input_gradient(self):
        changed = cloned(self.features)
        changed['active_mask'][1] = False
        changed['active_events'].requires_grad_(True)
        self.model(changed).sum().backward()
        self.assertEqual(torch.count_nonzero(changed['active_events'].grad[1]).item(), 0)
        self.assertGreater(changed['active_events'].grad.abs().sum().item(), 0)

    def test_raw_score_head_is_not_relu_or_probability_normalized(self):
        with torch.no_grad():
            for parameter in self.model.parameters():
                parameter.zero_()
            self.model.head[-1].bias.fill_(-2.)
        torch.testing.assert_close(self.model(self.features), torch.full((5,), -2.), rtol=0, atol=0)

    def test_reference_self_difference_is_exactly_zero(self):
        scores = self.model(self.features)
        for teacher_index in range(len(scores)):
            differences = scores - scores[teacher_index]
            self.assertEqual(differences[teacher_index].item(), 0.)

    def test_pure_synthetic_backward_is_finite_without_an_optimizer(self):
        scores = self.model(self.features)
        differences = scores - scores[2]
        target = torch.tensor([.001, -.001, 0., .002, -.003])
        residual = (differences - target) / .002
        loss = torch.where(residual.abs() <= 1, .5 * residual.square(), residual.abs() - .5).mean()
        loss.backward()
        gradients = [p.grad for p in self.model.parameters()]
        self.assertTrue(all(gradient is not None and torch.isfinite(gradient).all().item() for gradient in gradients))
        self.assertGreater(sum(gradient.abs().sum().item() for gradient in gradients), 0.)

    def test_in_memory_state_dict_roundtrip(self):
        buffer = io.BytesIO()
        torch.save(self.model.state_dict(), buffer)
        buffer.seek(0)
        restored = CounterfactualModel()
        restored.load_state_dict(torch.load(buffer, weights_only=True))
        torch.testing.assert_close(restored(self.features), self.model(self.features), rtol=0, atol=0)

    def test_unknown_or_missing_fields_are_rejected(self):
        for key in ('seed', 'world_id', 'N', 'previous_reward', 'events_dropped'):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'whitelist'):
                self.model(dict(self.features, **{key: torch.tensor(1.)}))
        changed = cloned(self.features)
        del changed['polygon']
        with self.assertRaisesRegex(ValueError, 'whitelist'):
            self.model(changed)

    def test_non_tensor_or_non_mapping_inputs_are_rejected(self):
        with self.assertRaises(TypeError):
            self.model(list(self.features.values()))
        changed = dict(self.features, actions=self.features['actions'].tolist())
        with self.assertRaises(TypeError):
            self.model(changed)

    def test_invalid_feature_shapes_and_counts_are_rejected(self):
        replacements = (
            ('global_features', torch.zeros(19)),
            ('channels', torch.zeros(19, 12)),
            ('channels', torch.zeros(20, 13)),
            ('polygon', torch.zeros(31, 2)),
            ('active_events', torch.zeros(4, 13)),
            ('active_events', torch.zeros(129, 14)),
            ('active_events', torch.zeros(0, 14)),
            ('actions', torch.zeros(10, 14)),
            ('actions', torch.zeros(0, 14)),
            ('actions', torch.zeros(5, 15)),
            ('active_mask', torch.ones(3, dtype=torch.bool)),
        )
        for key, value in replacements:
            with self.subTest(key=key, shape=tuple(value.shape)), self.assertRaises(ValueError):
                self.model(dict(self.features, **{key: value}))

    def test_mixed_or_empty_batches_are_rejected(self):
        batch = {key: value.unsqueeze(0) for key, value in self.features.items()}
        for key, value in (('actions', self.features['actions']),
                           ('channels', torch.zeros(2, 20, 12))):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.model(dict(batch, **{key: value}))
        with self.assertRaises(ValueError):
            self.model({key: value[:0] for key, value in batch.items()})

    def test_nonfinite_values_even_in_padding_are_rejected(self):
        for key in FEATURE_KEYS - {'active_mask'}:
            for poison in (float('nan'), float('inf'), -float('inf')):
                changed = cloned(self.features)
                changed[key].reshape(-1)[0] = poison
                with self.subTest(key=key, poison=poison), self.assertRaisesRegex(ValueError, 'nonfinite'):
                    self.model(changed)
        changed = cloned(self.features)
        changed['active_mask'][1] = False
        changed['active_events'][1, 0] = float('nan')
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            self.model(changed)

    def test_mask_dtype_and_empty_rows_are_rejected(self):
        with self.assertRaises(TypeError):
            self.model(dict(self.features, active_mask=torch.ones(4)))
        with self.assertRaisesRegex(ValueError, 'unmasked'):
            self.model(dict(self.features, active_mask=torch.zeros(4, dtype=torch.bool)))
        batch = {key: torch.stack((value, value)) for key, value in self.features.items()}
        batch['active_mask'][1] = False
        with self.assertRaisesRegex(ValueError, 'unmasked'):
            self.model(batch)

    def test_float_dtype_matches_parameters_and_double_model_works(self):
        with self.assertRaises(TypeError):
            self.model(dict(self.features, actions=self.features['actions'].to(torch.int64)))
        with self.assertRaises(TypeError):
            self.model(dict(self.features, actions=self.features['actions'].double()))
        doubled = {key: value if key == 'active_mask' else value.double()
                   for key, value in self.features.items()}
        scores = self.model.double()(doubled)
        self.assertEqual(scores.dtype, torch.float64)
        self.assertTrue(torch.isfinite(scores).all().item())

    def test_bad_parameter_output_is_rejected(self):
        with torch.no_grad():
            self.model.head[-1].bias.fill_(float('nan'))
        with self.assertRaisesRegex(ValueError, 'nonfinite action scores'):
            self.model(self.features)


if __name__ == '__main__':
    unittest.main()
