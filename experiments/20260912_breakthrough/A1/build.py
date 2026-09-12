"""Build a pinned self-contained candidate; generated snapshots are immutable."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
C7=ROOT/'experiments/20260911_stage4/combination/geometry_fusions/C7_both.py'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser()
p.add_argument('--round',required=True)
p.add_argument('--component',required=True)
p.add_argument('--description',required=True)
p.add_argument('--parent')
p.add_argument('--direction',default='D1 station task-cost gate')
args=p.parse_args()
assert sha(C7)=='cf37866829b9c6f376895075e819a732939e6fa8ad6d8d6297a151d7a213dcb3'
parent=HERE/args.parent if args.parent else C7
component=HERE/args.component
out=HERE/'snapshots'/f'{args.round}.py'
out.parent.mkdir(exist_ok=True)
assert not out.exists()
out.write_text(parent.read_text()+'\n'+component.read_text())
registration=dict(round=args.round,direction=args.direction,description=args.description,
                  parent=str(parent),parent_sha256=sha(parent),component=str(component),component_sha256=sha(component),
                  candidate=str(out),candidate_sha256=sha(out),tests=['rules','quick','full if retained','4800 exposed if retained'],
                  data_role='exposed local regression; not holdout or official',q4='unchanged dispatch to pinned parent',
                  gate='all complete; Q3 both batches improve against retained parent; no Q4 change')
(HERE/f'{args.round}_registration.json').write_text(json.dumps(registration,ensure_ascii=False,indent=2))
print(json.dumps(registration,ensure_ascii=False,indent=2))
