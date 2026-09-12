import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--config',default='{}');a=p.parse_args();conf=json.loads(a.config)
helpers=(HERE/'point_component.py').read_text().split('class ObservationResidualDirectional')[0]
source=(HERE/'snapshots/baseline.py').read_text()+'\n'+helpers+'\n'+(HERE/'bias_component.py').read_text()+'\nOPTIMIZED_CONFIGS[4].update('+repr(conf)+')\n'
path=HERE/'snapshots'/f'{a.name}.py';assert not path.exists();path.write_text(source)
(HERE/f'{a.name}_registration.json').write_text(json.dumps(dict(name=a.name,config=conf,
    candidate_sha256=hashlib.sha256(source.encode()).hexdigest(),direction='Q4 shared error online calibration',
    inputs='cleared-source public bearing records and successful clear/near disks; no exact truth',
    gate='all-clear quick, new development then full and paired 4800 if retained',
    independent_error_assumption=False,shared_bias_is_planning_hypothesis_only=True),indent=2))
print(path)
