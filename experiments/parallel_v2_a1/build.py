from pathlib import Path
import hashlib,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
r=sys.argv[1]
parent=ROOT/'experiments/20260912_breakthrough/A1/snapshots/r2.py'
assert hashlib.sha256(parent.read_bytes()).hexdigest()=='ba99196e9b7b61b5af50ba272f545148ed1bed618407d7711051c63b006cba01'
component=(HERE/'component.py').read_text().replace('TRIAL_VARIANT = 1','TRIAL_VARIANT = '+r)
text=parent.read_text()+'\n'+component+'\n'+(HERE/'service_method.txt').read_text()+'''
class Solver:
    def __new__(cls, env, mode=3, **config):
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return TrialSpatial(env,mode=mode,**merged)
        return _TRIAL_PARENT(env,mode=mode,**merged)
'''
p=HERE/'snapshots'/('r'+r+'.py');assert not p.exists();p.write_text(text)
(HERE/('r'+r+'_registration.json')).write_text(json.dumps(dict(round='r'+r,parent_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),mechanism='uniform-area optical trial with failure followup at actual trial point',variant=int(r),data_role='development selection and exposed regression; no holdout'),indent=2))
print(p)
