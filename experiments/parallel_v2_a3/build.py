import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--config',default='{}');p.add_argument('--component',default='point_component.py');a=p.parse_args()
conf=json.loads(a.config)
source=(HERE/'snapshots/baseline.py').read_text()+'\n'+(HERE/a.component).read_text()+'\nOPTIMIZED_CONFIGS[4].update('+repr(conf)+')\n'
path=HERE/'snapshots'/f'{a.name}.py'
assert not path.exists();path.write_text(source)
(HERE/f'{a.name}_registration.json').write_text(json.dumps(dict(name=a.name,config=conf,
    candidate_sha256=hashlib.sha256(source.encode()).hexdigest(),direction='Q4 angular observation residual',
    inputs='public bearing positions/angles, retained polygon, public action ledger only',
    gate='all-clear quick; independent development improvement; full and paired 4800 for retained',
    role='local development and exposed regression, no blind or official'),indent=2))
print(path)
