#!/usr/bin/env python3
"""Independent raw-artifact consistency audit; no solver or environment import."""
from pathlib import Path
import argparse
import hashlib
import json
import math


def polygon_area(p):
    return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(p,p[1:]+p[:1])))/2


def main():
    parser=argparse.ArgumentParser();parser.add_argument('out');args=parser.parse_args()
    out=Path(args.out);load=lambda name:json.loads((out/name).read_text())
    states={r['state_id']:r for name in ('synthetic_action_states.json','synthetic_coverage_states.json') for r in load(name)}
    actions=load('action_rows.json');coverage=load('coverage_rows.json');details=load('coverage_certificates.json')
    assert len(actions)==108*4 and len(coverage)==36*3
    assert len({(r['state_id'],r['arm']) for r in actions})==len(actions)
    assert len({(r['state_id'],r['arm']) for r in coverage})==len(coverage)
    action_details={r['state_id']:r for r in load('action_details.json')}
    checked_action_vertices=0;rejected=set()
    for row in actions:
        state=states[row['state_id']];detail=action_details[row['state_id']]
        if not row['single_clear_feasible']:
            assert row['empty_K_radius_lower_bound_m']>20.
            assert detail['empty_K_certificate']['radius_lower_bound_m']>20.
            rejected.add(row['state_id']);continue
        q=detail['points'][row['arm']]
        maximum=max(math.dist(q,v) for v in state['polygon'])
        assert maximum<=20.+2e-7
        assert abs(maximum-row['maximum_vertex_distance_m'])<1e-9
        checked_action_vertices+=len(state['polygon'])
    checked_cells=0;checked_cover_vertices=0
    for plan in details:
        points=plan['ordered_points'];certificate=plan['independent_union_certificate'];state=states[plan['state_id']]
        total=0.
        for cell in certificate['cells']:
            q=points[cell['disk_index']];verts=cell['vertices']
            assert all(math.dist(q,v)<=20.+2e-7 for v in verts)
            # Every checked cell vertex belongs to its assigned nearest-centre cell.
            assert all(math.dist(v,q)<=min(math.dist(v,z) for z in points)+2e-6 for v in verts)
            total+=polygon_area(verts);checked_cells+=1;checked_cover_vertices+=len(verts)
        assert abs(total-polygon_area(state['polygon']))<max(1e-5,polygon_area(state['polygon'])*1e-8)
    code=Path(__file__).resolve().parents[3]
    manifest=load('input_manifest.json')['sha256']
    assert all(hashlib.sha256((code/p).read_bytes()).hexdigest()==h for p,h in manifest.items())
    result=dict(passed=True,synthetic_states=len(states),action_rows=len(actions),coverage_rows=len(coverage),
        empty_K_states=len(rejected),certified_optical_plans=len(details),
        checked_action_vertices=checked_action_vertices,checked_voronoi_cells=checked_cells,
        checked_cover_vertices=checked_cover_vertices,all_input_hashes_match=True,
        evidence='Raw consistency and vertex/partition arithmetic audit. Continuous coverage additionally uses the stated convexity and Voronoi partition theorem; no source sampling is used as proof.')
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
