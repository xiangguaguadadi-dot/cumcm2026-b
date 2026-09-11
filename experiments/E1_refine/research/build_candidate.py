from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[3]
OWN=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def build(name,config,component='conditional_route_component.py'):
    p3=OWN/'parents/S1_Q3.py';p4=OWN/'parents/S1_Q4.py'
    # Literal parent bytes make this candidate a single hashed deployment file.
    header='"""Self-contained E1 candidate; embedded frozen parents are readable in ../parents/."""\nimport math,types\n'
    for label,path in [('_P3',p3),('_P4',p4)]:
        header+=f'{label}=types.ModuleType({label!r})\n{label}.__file__=__file__\nexec(compile({path.read_text()!r}, __file__+{label!r}, "exec"), {label}.__dict__)\n'
    code=(OWN/'research'/component).read_text()
    footer='\nOPTIMIZED_CONFIGS={3:dict(_P3.OPTIMIZED_CONFIGS[3]),4:dict(_P4.OPTIMIZED_CONFIGS[4],**'+repr(config)+')}\nBASELINE_CONFIG=dict(_P3.BASELINE_CONFIG)\nclass Solver:\n    def __new__(cls,env,mode=3,**config):\n        merged={**OPTIMIZED_CONFIGS[mode],**config}\n        if mode==3:return _P3.Solver(env,mode=mode,**merged)\n        return ConditionalDirectional(env,mode=mode,**merged)\n'
    target=OWN/'snapshots'/f'{name}.py';target.write_text(header+code+footer)
    return {'name':name,'file':str(target.relative_to(ROOT)),'sha256':sha(target),'config':config,'parents':{str(x.relative_to(ROOT)):sha(x)for x in (p3,p4)},'component_sha256':sha(OWN/'research'/component)}
if __name__=='__main__':
    result=[build('r1_parent',{'conditional_discovery':'off'}),build('r1_posterior',{'conditional_discovery':'posterior'}),build('r1_optimistic',{'conditional_discovery':'optimistic'})]
    (OWN/'research/r1_candidates.json').write_text(json.dumps(result,indent=2))
