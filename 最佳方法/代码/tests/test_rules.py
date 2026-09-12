import sys,unittest,math,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_env import LocalEnv,Source
class Rules(unittest.TestCase):
    def env(self,items=()):
        e=LocalEnv(items,keep_log=False);e.enter();return e
    def test_official_example(self):
        e=self.env()
        for a,x,y,ch in [('measure',300,400,1),('measure',300,400,2),('clear',300,0,3),('measure',300,0,2)]:getattr(e,a)(x,y,ch)
        self.assertEqual(e.exit()['virtual_time_s'],199);self.assertEqual(e.channel,2)
    def test_invalid_is_atomic(self):
        for action in ['measure','clear']:
            for args in [(300,400,0),(300,400,21),(300,400,True),(300,400,1.5),(True,400,1),(float('nan'),0,1),(2000001,0,1)]:
                e=self.env()
                with self.assertRaises(ValueError):getattr(e,action)(*args)
                self.assertEqual((e.position,e.channel,e.virtual_time_s),((0,0),1,0))
    def test_channel_integral_number(self):
        self.assertTrue(self.env().measure(0,0,1.0)['accepted'])
    def test_signed_zero(self):
        e=self.env([Source(1,1000,0,1000)])
        self.assertEqual(e.measure(0.,0.,1)['svd_deg'],e.measure(-0.,0.,1)['svd_deg'])
    def test_zero_cleared_undefined_average(self):self.assertIsNone(self.env().stats()['average_s'])
    def test_state_rejection(self):
        e=LocalEnv([]);self.assertFalse(e.measure(0,0,1)['accepted']);e.enter();e.measure(0,0,1)
        self.assertFalse(e.enter()['accepted'])
        self.assertEqual(e.virtual_time_s,5)
    def test_window_real_cutoff(self):
        now=[100.];e=LocalEnv([],clock=lambda:now[0],window_elapsed_s=600)
        self.assertEqual(e.enter()['remaining_real_duration_s'],900)
        now[0]+=900
        with self.assertRaises(ConnectionError):e.measure(300,400,1)
        self.assertEqual(e.position,(0,0));self.assertTrue(e.finished)
    def test_runtime_twenty_minutes(self):
        now=[100.];e=LocalEnv([],clock=lambda:now[0]);e.enter();now[0]+=1200
        with self.assertRaises(ConnectionError):e.clear(0,0,1)
        self.assertEqual(e.virtual_time_s,0)
    def test_inflight_completes_then_closes(self):
        e=self.env();e._virtual_us=359999_000000;e.virtual_time_s=359999
        self.assertEqual(e.measure(0,0,1)['virtual_time_s'],360004)
        with self.assertRaises(ConnectionError):e.measure(0,0,1)
        self.assertEqual(e.measures,1)
    def test_at_virtual_deadline(self):
        e=self.env();e._virtual_us=360000_000000;e.virtual_time_s=360000
        with self.assertRaises(ConnectionError):e.clear(300,400,1)
        self.assertEqual(e.position,(0,0))
    def test_clear_direction_independent_and_no_switch(self):
        e=self.env([Source(2,0,0,1000,0)])
        self.assertEqual(e.clear(-20,0,2)['clear_result'],'success');self.assertEqual(e.channel,1)
        self.assertEqual(e.clear(-20,0,2)['clear_result'],'no_target_in_range')
    def test_case_constraints(self):
        cases=json.loads((Path(__file__).resolve().parents[1]/'evaluation/cases_v1.json').read_text())
        self.assertEqual(len(cases),2400);self.assertEqual(sum(c['quick'] for c in cases),120)
        for c in cases:
            sources=c['sources'];self.assertTrue(10<=len(sources)<=16)
            self.assertEqual(len({s['channel'] for s in sources}),len(sources))
            for s in sources:self.assertTrue(math.hypot(s['x'],s['y'])<=1800+1e-8 and 1000<=s['radius']<=1500)
            nd=sum(s['direction'] is not None for s in sources)
            self.assertTrue(nd==0 if c['mode']==3 else 0<nd<len(sources))
if __name__=='__main__':unittest.main()
