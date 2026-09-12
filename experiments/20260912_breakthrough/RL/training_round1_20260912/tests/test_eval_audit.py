"""Pure wrappers: no environment construction, child process or model forward."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from ..evaluate_round import AuditedWorker
from ..common import digest

class EvaluationAuditTests(unittest.TestCase):
    def test_records_exact_public_snapshot_once_and_returns_same_response(self):
        response=dict(request_id='17',scores=[0.,.5]);inner=SimpleNamespace(checkpoint_sha='c'*64,disabled=False,
            score=Mock(return_value=response));worker=AuditedWorker(inner);worker.choice_id='choice';worker.prefix_event_count=29
        snapshot={'features':{'one':[1.,2.]},'teacher_id':'a','candidate_ids':['a','b']}
        self.assertIs(worker.score(snapshot),response);inner.score.assert_called_once_with(snapshot)
        row=worker.records[0]
        self.assertEqual(row['public_snapshot'],snapshot);self.assertEqual(row['public_snapshot_sha256'],digest(snapshot))
        self.assertEqual(row['public_prefix_event_count'],29);self.assertEqual(row['worker_request_id'],'17')
        self.assertEqual(row['choice_id'],'choice');self.assertEqual(row['raw_scores_float32'],[0.,.5])
        snapshot['features']['one'][0]=9.
        self.assertEqual(row['public_snapshot']['features']['one'][0],1.)

    def test_memory_error_preserves_attempted_input_and_propagates(self):
        inner=SimpleNamespace(checkpoint_sha='c'*64,disabled=False,score=Mock(side_effect=MemoryError('fixture')))
        worker=AuditedWorker(inner);worker.choice_id='choice';worker.prefix_event_count=7
        with self.assertRaises(MemoryError):worker.score({'public':'only'})
        self.assertEqual(len(worker.records),1);self.assertFalse(worker.records[0]['success'])
        self.assertIn('MemoryError',worker.records[0]['error']);inner.score.assert_called_once()

    def test_reset_clears_only_episode_audit_not_actual_worker_state(self):
        inner=SimpleNamespace(checkpoint_sha='c'*64,disabled=True,score=Mock())
        worker=AuditedWorker(inner);worker.records=[{'old':'row'}];worker.choice_id='old';worker.prefix_event_count=3
        worker.reset_episode();self.assertEqual(worker.records,[]);self.assertIsNone(worker.choice_id)
        self.assertTrue(worker.disabled);self.assertEqual(worker.checkpoint_sha,'c'*64);inner.score.assert_not_called()

if __name__=='__main__':unittest.main()
