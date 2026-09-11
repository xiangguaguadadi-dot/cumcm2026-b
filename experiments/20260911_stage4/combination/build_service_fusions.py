"""Finite interactions between completed route and service components."""
import ast
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
TREES=ROOT.parent

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def class_source(path,name):
    s=path.read_text()
    n=next(n for n in ast.parse(s).body if isinstance(n,ast.ClassDef) and n.name==name)
    return ast.get_source_segment(s,n)

def main():
    out=HERE/'service_fusions'
    out.mkdir(exist_ok=True)
    p1=HERE/'snapshots/C1_combined.py'
    p2=ROOT/'experiments/E2_refine/snapshots/r2_one_round.py'
    p3=TREES/'E1_refine/experiments/E1_refine/snapshots/r5_immediate_block.py'
    assert sha(p1)=='dc7e88a92b677e7b632c66aaf8317b85855db298d581fc12d2fd2e1cbe4582d2'
    assert sha(p2)=='7f486891b0255054cb05dcf749ecd7b1ecbfec49b1834670a0c3b466c18d8fd6'
    assert sha(p3)=='f8413f0017d5699e6d1e06b2f8c85d2e86c0f6b69afc32a29377dbda8907d604'
    registry={}
    def put(name,source,role):
        dest=out/(name+'.py')
        if dest.exists(): assert dest.read_text()==source
        else: dest.write_text(source)
        registry[name]={'file':str(dest.relative_to(HERE)), 'sha256':sha(dest),'role':role,'dependencies':{}}
    put('C1',p1.read_text(),'previous combined best')
    put('E2_R2',p2.read_text(),'current Q4 best')
    put('E1_R5',p3.read_text(),'independent immediate-entry route control')
    service=class_source(p2,'ServiceDirectional')
    def footer(config,klass):
        return ('\nOPTIMIZED_CONFIGS[4].update('+repr(config)+')\nclass Solver:\n'
                '    def __new__(cls,env,mode=3,**config):\n'
                '        if mode not in (3,4):raise ValueError("mode must be 3 or 4")\n'
                '        merged={**OPTIMIZED_CONFIGS[mode],**config}\n'
                '        if mode==3:return _Q3.Solver(env,mode=mode,**merged)\n'
                f'        return {klass}(env,mode=mode,**merged)\n')
    put('C2_conditional_round',p1.read_text()+'\n'+service+footer({'e2_one_round':True,'e2_same_here':False},'ServiceDirectional'),'new conditional route plus persistent round')
    put('C2_route_off',p1.read_text()+'\n'+service+footer({'e2_one_round':True,'e2_same_here':False,'conditional_discovery':'off'},'ServiceDirectional'),'wiring check against E2_R2')
    header=('"""Immediate-entry route with station cost gate; frozen component composition."""\n'
            'import types,math\n_R5=types.ModuleType("frozen_E1_R5")\n_R5.__file__=__file__\n'
            f'exec(compile({p3.read_text()!r},"<E1-R5>","exec"),_R5.__dict__)\n'
            '_Q3=_R5._P3\n_Q4=_R5._P4\n'
            'OPTIMIZED_CONFIGS={3:dict(_Q3.OPTIMIZED_CONFIGS[3]),4:dict(_R5.OPTIMIZED_CONFIGS[4])}\n'
            'BASELINE_CONFIG=dict(_Q3.BASELINE_CONFIG)\n')
    cost=class_source(p2,'CostDirectional')
    assert cost.count('class CostDirectional(_Q4._LensDirectional):')==1
    cost=cost.replace('class CostDirectional(_Q4._LensDirectional):','class CostDirectional(_R5.BlockDirectional):',1)
    base=header+cost+'\n'
    settings={'e2_opportunity':'parent','e2_station_cost':True,'e2_same_here':False}
    put('C3_entry_station',base+footer(settings,'CostDirectional'),'immediate-entry route with station gate, no conditional cancellation')
    put('C3_gate_off',base+footer({**settings,'e2_station_cost':False},'CostDirectional'),'Q4 wiring check against E1_R5; Q3 deliberately retains S1')
    put('C4_entry_round',base+service+footer({**settings,'e2_one_round':True},'ServiceDirectional'),'entry-route/persistent-round interaction; forecast exit need not equal actual end of one round')
    manifest={'candidates':registry,'wiring_pairs':[['C2_route_off','E2_R2'],['C3_gate_off','E1_R5']],
              'parents':{'C1':sha(p1),'E2_R2':sha(p2),'E1_R5':sha(p3)},
              'hypothesis':'Test component interactions on new development before complete regression. No predicted additive gain.',
              'selection':'All normal/clear, then Q4 mean over all new cases. Promote only a useful change beyond E2_R2.'}
    (out/'registry.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({n:r['sha256'] for n,r in registry.items()},indent=2))

if __name__=='__main__':main()
