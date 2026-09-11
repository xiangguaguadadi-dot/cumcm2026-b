"""Last bounded component interaction: conservative optical/radio exclusions."""
import ast,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source(path,name,kind):
    s=path.read_text();n=next(n for n in ast.parse(s).body if isinstance(n,kind) and n.name==name)
    return ast.get_source_segment(s,n)

def main():
    out=HERE/'geometry_fusions';out.mkdir(exist_ok=True)
    parent=HERE/'service_fusions/C2_conditional_round.py'
    cells=ROOT.parent/'E2_refine/experiments/E2_refine/snapshots/r3_failure_cells.py'
    wedge=ROOT/'experiments/E3_expand/snapshots/r3.py'
    expected={parent:'3c57f38a15231602fb8f8435b3379669857d25764cc30661cef629967f00aa91',
              cells:'5d3e8c1ba1f1bd26a326dbd1241776177e2c8902b5a2a6a8f87982925cbade09',
              wedge:'7d113e5262d52eaca7e0287ea062e3221b0cadf33340f3536b2b1adbe8f7ec27'}
    for p,h in expected.items():assert sha(p)==h
    failure=source(cells,'FailureDirectional',ast.ClassDef)
    funcs=source(wedge,'exclude_forced_visible_wedge',ast.FunctionDef)+'\n'+source(wedge,'area',ast.FunctionDef)
    funcs=funcs.replace('_d._di_clip','_Q4._di_clip').replace('_s1._A1._geo_convex_hull','_Q3._geo_convex_hull')
    negative=source(wedge,'_Directional',ast.ClassDef)
    assert negative.count('class _Directional(_d._LensDirectional):')==1
    negative=negative.replace('class _Directional(_d._LensDirectional):','class GeometryDirectional(FailureDirectional):',1)
    common=parent.read_text()+'\n'+failure+'\n'+funcs+'\n'+negative+'\n'
    registry={'C2':{'file':str(parent.relative_to(HERE)),'sha256':sha(parent),'role':'current best'}}
    for name,cell_flag,wedge_flag in [('C5_cells',True,False),('C6_wedge',False,True),('C7_both',True,True),('C7_off',False,False)]:
        config=dict(e2_failure_hull=False,e2_failure_cells=cell_flag,convex_no_signal=wedge_flag)
        code=common+'\nOPTIMIZED_CONFIGS[4].update('+repr(config)+')\n'+'''class Solver:
    def __new__(cls,env,mode=3,**config):
        if mode not in (3,4):raise ValueError('mode must be 3 or 4')
        merged={**OPTIMIZED_CONFIGS[mode],**config}
        if mode==3:return _Q3.Solver(env,mode=mode,**merged)
        return GeometryDirectional(env,mode=mode,**merged)
'''
        p=out/(name+'.py')
        if p.exists():assert p.read_text()==code
        else:p.write_text(code)
        registry[name]={'file':str(p.relative_to(HERE)),'sha256':sha(p),'config':config,
                        'role':'wiring check' if name=='C7_off' else 'new conservative exclusion combination',
                        'dependencies':{}}
    manifest=dict(candidates=registry,wiring_pairs=[['C7_off','C2']],
                  parents={str(p):h for p,h in expected.items()},
                  hypothesis='Test optical-cell and radio-negative exclusions on the current retained action schedule; reliable information need not reduce total task time.',
                  selection='All clear/normal, then lower all-case Q4 mean than C2. Only useful candidate is promoted, with all negative interactions retained.')
    (out/'registry.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v['sha256'] for k,v in registry.items()},indent=2))

if __name__=='__main__':main()
