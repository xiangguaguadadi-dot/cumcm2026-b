"""Reconstruct all three frozen variants and verify the declared differences."""
from pathlib import Path
import hashlib,json

root=Path(__file__).resolve().parent
parent=(root.parent/'baseline.py').read_text()
assert hashlib.sha256(parent.encode()).hexdigest()=='0bda4f711b9e9716739af8aedf456cb1eeefb47d8ba3ed230ca682c8450a96ea'
prefix='import types\n_P=types.ModuleType("frozen_fusion_r5")\n_P.__file__=__file__\nexec(compile('+repr(parent)+',__file__+":parent","exec"),_P.__dict__)\n'
b1=prefix+(root/'mechanism.py').read_text()
b2=b1.replace('kept.append((rad[0],cost,tuple(q)))','kept.append((cost,rad[0],tuple(q)))')
added='''        # B3 local refinement fills gaps between fixed 60/160 m offsets using
        # the inherited point's actual polygon-adaptive advance and lateral.
        pa=sum((parent[k]-p[k])*u[k] for k in (0,1))
        pl=sum((parent[k]-p[k])*v[k] for k in (0,1))
        for forward_scale in (.8,1.,1.25):
            for side_scale in (.8,1.,1.25):
                out.append((p[0]+forward_scale*pa*u[0]+side_scale*pl*v[0],
                            p[1]+forward_scale*pa*u[1]+side_scale*pl*v[1]))
'''
anchor='        # A cheap short move toward the current route-local parent candidate.\n'
b3=b2.replace(anchor,added+anchor)
checks=[]
for name,text,reg in (('B1_minimax_costgate.py',b1,'B1_REGISTRATION.json'),
                      ('B2_cost_precisiongate.py',b2,'B2_REGISTRATION.json'),
                      ('B3_local_refinement.py',b3,'B3_REGISTRATION.json')):
    p=root/name;actual=p.read_bytes();digest=hashlib.sha256(actual).hexdigest()
    check=dict(candidate=name,reconstructed_identical=actual==text.encode(),
               registered_hash_matches=digest==json.loads((root/reg).read_text())['sha256'],sha256=digest)
    checks.append(check)
out=dict(parent_sha256=hashlib.sha256(parent.encode()).hexdigest(),checks=checks,
         all_passed=all(c['reconstructed_identical'] and c['registered_hash_matches'] for c in checks))
(root/'BUILD_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
assert out['all_passed']
