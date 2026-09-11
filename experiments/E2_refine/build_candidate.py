"""Embed unchanged S1 components so a snapshot has no deployment dependencies."""
from pathlib import Path
import json,hashlib,argparse
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
BASE=ROOT/'experiments/20260911_stage4/baseline'
VARIANTS={'r1_parent':dict(e2_opportunity='parent',e2_station_cost=False),
          'r1_off':dict(e2_opportunity='off',e2_station_cost=False),
          'r1_cost_opportunity':dict(e2_opportunity='cost',e2_station_cost=False),
          'r1_cost_all':dict(e2_opportunity='cost',e2_station_cost=True),
          'r1_station_only':dict(e2_opportunity='parent',e2_station_cost=True),
          'r1_station_uncertified':dict(e2_opportunity='parent',e2_station_cost=True,e2_station_mode='uncertified')}

def main():
 p=argparse.ArgumentParser();p.add_argument('names',nargs='*');a=p.parse_args()
 sources={k:(BASE/f).read_text() for k,f in [('Q3','R2_open_R4.py'),('Q4','R3_open_R5.py')]}
 component=(HERE/'cost_component.py').read_text()
 for name in a.names or VARIANTS:
  code='"""E2 stage-four '+name+': complete, self-contained S1-derived strategy.\nQ3 retains S1. Finite proxies only rank legal actions; no case data is loaded.\n"""\nimport types\n'
  for key,source in sources.items():
   code+=f'_{key}=types.ModuleType("e2_frozen_{key}")\n_{key}.__file__=__file__\nexec(compile({source!r},"<frozen-S1-{key}>","exec"),_{key}.__dict__)\n'
  code+='\n'+component+'\nOPTIMIZED_CONFIGS[4].update('+repr(VARIANTS[name])+')\n'
  path=HERE/'snapshots'/(name+'.py');path.write_text(code)
  meta={'candidate':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'q4_config':VARIANTS[name],
        'parents':{f:hashlib.sha256((BASE/f).read_bytes()).hexdigest() for f in ['R2_open_R4.py','R3_open_R5.py']},'component_sha256':hashlib.sha256(component.encode()).hexdigest(),'deployment_dependencies':{}}
  path.with_suffix('.provenance.json').write_text(json.dumps(meta,indent=2)+'\n')
  print(name,meta['sha256'])
if __name__=='__main__':main()
