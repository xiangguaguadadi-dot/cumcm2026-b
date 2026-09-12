"""Freeze the parent and mechanism; output is a standalone candidate."""
from pathlib import Path
import hashlib,json,datetime

root=Path(__file__).resolve().parent
parent=root.parent/'baseline.py'
baseline=parent.read_text()
assert hashlib.sha256(parent.read_bytes()).hexdigest()=='0bda4f711b9e9716739af8aedf456cb1eeefb47d8ba3ed230ca682c8450a96ea'
body=(root/'mechanism.py').read_text()
dest=root/'B1_minimax_costgate.py'
if dest.exists():raise RuntimeError('candidate already frozen')
dest.write_text('import types\n_P=types.ModuleType("frozen_fusion_r5")\n_P.__file__=__file__\nexec(compile('+repr(baseline)+',__file__+":parent","exec"),_P.__dict__)\n'+body)
record={'registered_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'candidate':dest.name,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
        'parent_sha256':hashlib.sha256(parent.read_bytes()).hexdigest(),
        'mechanism':'Current-polygon variable-length measurement candidates; continuous future-bearing MEC bound; full next-measure-plus-clear surrogate cost and Q4 visibility gate; precision-first Pareto choice.',
        'limits':{'candidate_locations':14,'future_angle_splits':32,'planning_targets':9,'planning_errors':3},
        'invariants':['unmodified authoritative polygons','unmodified certified clears','unmodified full discovery','unmodified finite fallback'],
        'planned_evaluation':['nominal','quick','full if promising','exposed if retained'],
        'maximum_substantive_versions':3,
        'B2_if_needed':'Task-cost-first choice under the same future precision and visibility gates',
        'B3_if_needed':'Bounded local candidate refinement justified by observed failure mechanism'}
(root/'B1_REGISTRATION.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(record,ensure_ascii=False,indent=2))
