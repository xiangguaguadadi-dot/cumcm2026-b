import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluate import summarize
class Metrics(unittest.TestCase):
    def row(self,v,complete,t):return dict(mode=3,group='g',variant=v,complete=complete,error=None,average_clear_time_s=t,program_runtime_s=.01)
    def test_failure_is_not_filtered_into_speedup(self):
        z=summarize([self.row('frozen_baseline',True,100),self.row('candidate',False,1)])[0]
        self.assertFalse(z['time_comparison_valid']);self.assertNotIn('reduction_fraction',z)
    def test_paired_group_mean(self):
        z=summarize([self.row('frozen_baseline',True,100),self.row('candidate',True,80)])[0]
        self.assertAlmostEqual(z['reduction_fraction'],.2)
if __name__=='__main__':unittest.main()
