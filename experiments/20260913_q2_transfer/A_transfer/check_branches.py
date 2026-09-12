"""Public-state synthetic checks, not benchmark/official claims."""
import importlib.util,json,math,pathlib,hashlib,argparse
HERE=pathlib.Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--candidate',default='candidate_A1.py');args=parser.parse_args()
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
candidate=load(HERE/args.candidate,'transfer_candidate')
baseline=load(HERE.parent/'baseline.py','frozen_reference')
class NoActionEnv:
    def enter(self):raise AssertionError('unexpected environment action')
    def measure(self,*args):raise AssertionError('unexpected environment action')
    def clear(self,*args):raise AssertionError('unexpected environment action')
    def exit(self):raise AssertionError('unexpected environment action')
rows=[]
for mode in (3,4):
    for origin,degree in [((0.,0.),0.),((1400.,0.),0.),((0.,1200.),270.)]:
        for position in [(0.,0.),(600.,600.),(400.,-300.),(1200.,200.)]:
            a=candidate.Solver(NoActionEnv(),mode=mode);b=baseline.Solver(NoActionEnv(),mode=mode)
            poly=candidate._Q3._Q3._sp_add_bearing(candidate._Q3._Q3._sp_initial_polygon(),origin,degree)
            for s in (a,b):
                s.observations[1]=[(origin,degree)];s.polygons[1]=poly[:];s.position=position
            old=b.second_point(1);new=a.second_point(1)
            assert a.polygons[1]==poly and a.observations[1]==[(origin,degree)] and a.trace==[]
            assert math.dist(position,new)<=math.dist(position,old)+1e-6
            changed=math.dist(old,new)>1e-6
            if changed:
                assert abs(math.dist(origin,new)-math.dist(origin,old))<1e-6
                rr_old=candidate._q2a_worst_radius(poly,old);rr_new=candidate._q2a_worst_radius(poly,new)
                assert rr_new<.97*rr_old
                if mode==4:assert a.predicted_visibility(1,new)>=a.predicted_visibility(1,old)-.01000001
            rows.append({'mode':mode,'origin':origin,'bearing':degree,'current_position':position,'old':old,'new':new,'changed':changed,'passed':True})
out={'candidate_sha256':hashlib.sha256((HERE/args.candidate).read_bytes()).hexdigest(),'checks':'no environment action, no reliable geometry/observation mutation, current incoming movement cap, equal first-baseline length, lower minimax radius on selection, Q4 visibility prior gate','passed':True,'cases':len(rows),'changed':sum(r['changed'] for r in rows),'rows':rows}
(HERE/('checks_'+pathlib.Path(args.candidate).stem.removeprefix('candidate_')+'.json')).write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2))
