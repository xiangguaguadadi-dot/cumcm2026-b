"""Four synthetic failure/recovery fixtures; zero task-world executions."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

EXEC=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(EXEC/'runners'),str(EXEC)]
import common
import train_initialization as train

def example():
    w={'world_id':'synthetic-audit-only','mode':3,'group':'fixture','index':0}
    stats={'n':10,'cleared':10,'fraction':1.,'time_s':10.,'average_s':1.}
    raw={'decisions':[],'business_primitive_count':2,'success':True,'total_time_s':10.,
         'cost_partition_error_s':0.,'prefix_time_s':10.,'tail_time_s':0.}
    entry={'world_id':w['world_id'],'recipe':w,'label':'fixture','raw':raw,
        'terminal_labels':{'stats':stats,'true_n':10,'success':True,'error':None,'validation_errors':[]},
        'actual_calls':{'enter':1,'measure':1,'clear':0,'exit':0},'business_primitives':2,
        'execution_wall_s':.01,'peak_process_mib':1.,'collector_rng_after':[1,2,3]}
    return w,entry

class RunnerRecoveryFixtures(unittest.TestCase):
    def test_failed_terminal_validation_retains_executed_calls(self):
        w,entry=example();order=[]
        class Fake:
            finished=True;exit_reason='user_exit'
            def __init__(self,*a,**kw):pass
            def enter(self):order.append('enter');return {}
            def measure(self,*a):order.append('measure');return {}
            def clear(self,*a):return {}
            def exit(self):return {}
            def stats(self):order.append('truth');return entry['terminal_labels']['stats']
        def inconsistent(api,**kw):
            api.enter();api.measure(0,0,1)
            raw=dict(entry['raw']);raw['total_time_s']=99.
            return raw
        w.update(seed=1,noise='synthetic')
        with patch.object(common,'LocalEnv',Fake),patch.object(common,'instantiate',lambda w:[]),patch.object(common,'run_episode',inconsistent):
            result=common.execute(w,None,'fixture')
        self.assertEqual(order,['enter','measure','truth'])
        self.assertEqual(result['business_primitives'],2)
        self.assertFalse(result['terminal_labels']['success'])
        self.assertFalse(result['terminal_labels']['integrity_valid'])
        self.assertEqual(result['raw']['total_time_s'],99.)

    def test_orphan_archive_recovers_without_environment_reexecution(self):
        w,entry=example()
        with tempfile.TemporaryDirectory(dir=EXEC,prefix='.runner-fixture-') as tmp:
            out=Path(tmp);p=out/'episodes/q3_0000.json.gz';common.save_episode(p,entry)
            with patch.object(train,'execute',side_effect=AssertionError('must not execute')):
                recovered,path=train.collected_episode(out,w,'fixture',None,lambda:[])
            self.assertEqual(recovered['collector_rng_after'],[1,2,3])
            row=train.rows_at(out)[0]
            self.assertEqual(row['business_primitives'],2)
            self.assertTrue(row['storage']['storage_timing_unavailable'])
            self.assertEqual(train.verified_read(path)['world_id'],w['world_id'])
            path.write_bytes(path.read_bytes()+b'corruption')
            with self.assertRaisesRegex(RuntimeError,'SHA256 changed'):train.verified_read(path)

    def test_pending_execution_blocks_silent_repeat(self):
        w,entry=example()
        with tempfile.TemporaryDirectory(dir=EXEC,prefix='.runner-fixture-') as tmp:
            out=Path(tmp);path=out/'episodes/q3_0000.json.gz'
            common.dump(path.with_suffix('.started.json'),{'reserved_calls':15846})
            with patch.object(train,'execute',side_effect=AssertionError('must not execute')):
                with self.assertRaisesRegex(RuntimeError,'interrupted execution'):
                    train.collected_episode(out,w,'fixture',None,lambda:[])
            self.assertFalse((out/'rows.jsonl').exists())

    def test_update_commit_recovery_and_unknown_interrupted_compute(self):
        with tempfile.TemporaryDirectory(dir=EXEC,prefix='.runner-fixture-') as tmp:
            out=Path(tmp);resume=out/'resume.pt'
            train.start_update(out,'step1',4)
            state={'last_update':{'log':'updates.jsonl','record':{'commit_id':'step1','optimizer_steps':4}}}
            train.save_state(resume,state)  # interrupted after atomic state, before log
            train.recover_update(out,resume);train.recover_update(out,resume)
            self.assertEqual(len((out/'updates.jsonl').read_text().splitlines()),1)
            self.assertFalse((out/'interrupted_compute.jsonl').exists())
            train.start_update(out,'step2',4)  # no matching committed state
            train.recover_update(out,resume)
            item=json.loads((out/'interrupted_compute.jsonl').read_text())
            self.assertFalse(item['environment_reexecution'])
            self.assertIn('unknown',item['actual_optimizer_steps'])

if __name__=='__main__':unittest.main()
