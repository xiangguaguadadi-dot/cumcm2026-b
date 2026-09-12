"""State-level geometry only; no hidden world or local_env is imported.

Continuous union coverage is checked independently using clipped Voronoi cells.
Within each nearest-centre cell, vertex containment certifies the entire cell.
"""
from pathlib import Path
from types import SimpleNamespace
import ast
import csv
import hashlib
import importlib.util
import itertools
import json
import math
import platform
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
CODE = HERE.parents[2]
R = 20.0
EPS = 1e-7


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, tuple)) else v
                             for k, v in row.items()})


def load_solver(reg):
    path = CODE / reg['source_solver']
    assert sha(path) == reg['expected_solver_sha256'], 'B3 source hash changed'
    spec = importlib.util.spec_from_file_location('highlight_geometry_unchanged_B3', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    blocks = set()
    def visit(source):
        h = hashlib.sha256(source.encode()).hexdigest()
        if h in blocks:
            return
        blocks.add(h)
        for node in ast.walk(ast.parse(source)):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'compile' and node.args
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                visit(node.args[0].value)
    visit(path.read_text())
    matches = []
    for p in sorted((CODE / 'experiments/parallel_v2_coordinator/inspection_fusion_r5').glob('module_*.py')):
        matches.append(dict(path=str(p.relative_to(CODE)), sha256=sha(p), exactly_embedded=sha(p) in blocks))
    assert all(x['exactly_embedded'] for x in matches)
    return module, matches


def area(poly):
    return abs(sum(a[0]*b[1]-a[1]*b[0] for a, b in zip(poly, poly[1:]+poly[:1]))) / 2 if len(poly)>2 else 0.


def rotate(poly, degrees, offset=(0., 0.), scale=1.):
    a = math.radians(degrees); c, s = math.cos(a), math.sin(a)
    return [(offset[0]+scale*(c*x-s*y), offset[1]+scale*(s*x+c*y)) for x, y in poly]


def to_tuple(poly):
    return [tuple(map(float, q)) for q in poly]


def family_shapes():
    return {
        'long_strip': [(-45., -4.), (45., -4.), (45., 4.), (-45., 4.)],
        'spindle': [(-30., -6.), (0., -12.), (30., -6.), (30., 6.), (0., 12.), (-30., 6.)],
        'slanted_narrow': [(-44., -8.), (43., 3.), (40., 10.), (-40., -1.)],
        'near_circle': [(30.*math.cos(2*math.pi*k/24), 28.*math.sin(2*math.pi*k/24)) for k in range(24)],
        'critical_radius': [(20.*math.cos(2*math.pi*k/12), 20.*math.sin(2*math.pi*k/12)) for k in range(12)],
        'skew_triangle': [(-42., -10.), (42., 0.), (-26., 18.)],
    }


def build_synthetic(G, reg):
    coverage = []; actions = []
    for family, raw in family_shapes().items():
        raw = G._geo_convex_hull(raw)
        c0, r0 = G._sp_enclosing_circle(raw)
        centered = [(x-c0[0], y-c0[1]) for x, y in raw]
        for scale in reg['coverage_scales']:
            for rotation in reg['coverage_rotations_deg']:
                p = rotate(centered, rotation, (100., 50.), scale)
                a = math.radians(rotation)
                start = (100.-100.*math.cos(a), 50.-100.*math.sin(a))
                coverage.append(dict(state_id=f'syn-cover-{family}-{scale}-{rotation}', family=family,
                    evidence='synthetic_state_mechanism', mode=3, polygon=p, position=start,
                    successor=(200., 80.), observations=[], no_signal_points=[], failed_clear_points=[],
                    grid_origin=(100., 50.), grid_angle_deg=rotation, scale=scale, rotation_deg=rotation))
        for radius in reg['action_radii_m']:
            for j, (s, t) in enumerate(zip(reg['action_start_offsets_m'], reg['action_successor_offsets_m'])):
                p = rotate(centered, 23., (100., 50.), radius/r0)
                actions.append(dict(state_id=f'syn-action-{family}-{radius}-{j}', family=family,
                    evidence='synthetic_state_mechanism', mode=3, polygon=p,
                    position=(100.+s[0], 50.+s[1]), successor=(100.+t[0], 50.+t[1]),
                    requested_radius_m=radius))
    return coverage, actions


class PublicAPI:
    __slots__ = ('enter', 'measure', 'clear', 'exit')
    def __init__(self, replay):
        self.enter, self.measure, self.clear, self.exit = replay.enter, replay.measure, replay.clear, replay.exit


class Replay:
    """Only previously recorded public replies are returned to unchanged B3."""
    def __init__(self, row, G):
        self.row = row; self.trace = row['public_trace']; self.G = G
        self.i = 0; self.solver = None; self.coverage = {}; self.action = {}
        self.max_coordinate_delta = 0.; self.exited = False

    def enter(self):
        return dict(accepted=True, virtual_time_s=0., remaining_real_duration_s=1200)

    def capture(self, channel):
        obj = self.solver
        if channel in obj.cleared or channel not in obj.polygons:
            return
        poly = obj.polygons[channel]
        if not poly or len(poly)>64:
            return
        c, r = self.G._sp_enclosing_circle(poly)
        bins = [((20, 45), self.coverage, 'coverage'), ((45, 100), self.coverage, 'coverage'),
                ((100, 185), self.coverage, 'coverage'), ((0, 5), self.action, 'action'),
                ((5, 10), self.action, 'action'), ((10, 15), self.action, 'action'),
                ((15, 20), self.action, 'action')]
        for (lo, hi), destination, kind in bins:
            key = f'{lo}-{hi}'
            if not (lo < r <= hi) or key in destination:
                continue
            if kind == 'coverage' and area(poly)<1e-8:
                continue
            observations = obj.observations[channel]
            failed = getattr(obj, 'failed_clear_points', getattr(obj, '_e2_failed_clear', {})).get(channel, [])
            destination[key] = dict(state_id=f"public-{self.row['case_id']}-{kind}-{key}",
                evidence='replayed_public_state_mechanism', family=f'public_radius_{key}', mode=self.row['mode'],
                case_id=self.row['case_id'], group=self.row['group'], trace_index=self.i, channel=channel,
                polygon=[tuple(v) for v in poly], position=tuple(obj.position),
                successor=getattr(obj, 'route_successor', None), observations=observations[:],
                no_signal_points=obj.no_signal_points[channel][:], failed_clear_points=failed[:],
                grid_origin=observations[0][0] if observations else (0.,0.),
                grid_angle_deg=observations[0][1] if observations else 0.)

    def act(self, action, x, y, channel):
        assert self.i < len(self.trace), 'Solver emitted an extra action'
        expected = self.trace[self.i]
        assert action == expected['action'] and int(channel) == expected['channel'], (self.i, action, expected)
        delta = math.dist((x,y), (expected['x'],expected['y']))
        self.max_coordinate_delta = max(self.max_coordinate_delta, delta)
        assert delta < 1e-7, (self.row['case_id'], self.i, delta)
        self.capture(int(channel))
        self.i += 1
        result = dict(accepted=True, virtual_time_s=expected['virtual_time_s'])
        if action == 'measure':
            result.update(measure_result=expected['result'], svd_deg=expected.get('svd_deg'))
        else:
            result['clear_result'] = expected['result']
        return result

    def measure(self, x, y, channel):
        return self.act('measure', x, y, channel)

    def clear(self, x, y, channel):
        return self.act('clear', x, y, channel)

    def exit(self):
        assert self.i == len(self.trace), 'Solver exited before consuming the public trace'
        self.exited = True
        return dict(accepted=True, virtual_time_s=self.trace[-1]['virtual_time_s'], exit_reason='user_exit')


def replay_public(module, reg):
    # Aggregate source counts/timing in this file are not given to any planner.
    rows = json.loads((CODE / reg['public_trace_source']).read_text())
    coverage = []; actions = []; audit = []
    for row in rows:
        replay = Replay(row, module._G)
        solver = module.Solver(PublicAPI(replay), mode=row['mode'])
        replay.solver = solver
        result = solver.run()
        assert replay.exited
        assert abs(result['virtual_time_s']-row['total_virtual_time_s']) < 1e-6
        coverage.extend(replay.coverage.values()); actions.extend(replay.action.values())
        audit.append(dict(case_id=row['case_id'], mode=row['mode'], group=row['group'],
            public_actions=len(replay.trace), matched_actions=replay.i,
            max_coordinate_delta_m=replay.max_coordinate_delta,
            exact_virtual_time_match=result['virtual_time_s']==row['total_virtual_time_s'],
            coverage_states=len(replay.coverage), action_states=len(replay.action),
            complete_trace_consumed=replay.exited, new_world_execution=False))
    return coverage, actions, audit


def inner_point(position, center, radius, margin=1e-6):
    allowance = max(0., R-radius-margin)
    d = math.dist(position,center)
    if d <= allowance:
        return tuple(position)
    if d == 0.:
        return tuple(center)
    return tuple(center[k]+allowance*(position[k]-center[k])/d for k in (0,1))


def action_points(G, state):
    poly = to_tuple(state['polygon']); start = tuple(state['position'])
    target = tuple(state['successor']) if state.get('successor') is not None else None
    center, radius = G._sp_enclosing_circle(poly)
    if radius>R+1e-8:
        return center, radius, None
    def compute(arm):
        # Include the common MEC and the route parent's inner-disk fallback
        # in each measured algorithm call, not only the final boundary search.
        cc,rr=G._sp_enclosing_circle(poly)
        if arm=='mec_center':return cc
        if arm=='inner_safe_disk':return inner_point(start,cc,rr)
        dummy=SimpleNamespace(position=start,route_successor=target)
        if arm=='full_K_nearest':return G._LensSpatial.nearest_certified_clear(dummy,poly,cc,rr)
        original=inner_point(start,cc,rr)
        fallback=G._sp_Solver.route_clear_point(dummy,cc,rr,original)
        return G._lens_route_point(poly,start,target,fallback)
    return center,radius,{arm:(lambda arm=arm:compute(arm)) for arm in
        ('mec_center','inner_safe_disk','full_K_nearest','full_K_route')}


def radius_lower_witness(poly):
    """Independent lower bound: exact-form MEC radius of a 2/3-point subset."""
    best=(0.,[])
    for a,b in itertools.combinations(poly,2):
        rr=math.dist(a,b)/2
        if rr>best[0]:best=(rr,[a,b])
    for a,b,c in itertools.combinations(poly,3):
        sides=sorted((math.dist(a,b),math.dist(a,c),math.dist(b,c)))
        if sides[2]**2>=sides[0]**2+sides[1]**2:
            rr=sides[2]/2
        else:
            cross=abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
            if cross<1e-15:continue
            rr=sides[0]*sides[1]*sides[2]/(2*cross)
        if rr>best[0]:best=(rr,[a,b,c])
    return dict(radius_lower_bound_m=best[0],points=best[1],
        proof='Any enclosing disk must enclose this 2/3-point subset; obtuse/right triples use half longest side, acute triples use circumradius.')


def run_action_states(G, states):
    rows = []; details = []
    for state in states:
        c, r, methods = action_points(G,state)
        common = dict(state_id=state['state_id'], evidence=state['evidence'], family=state['family'],
            mode=state['mode'], vertices=len(state['polygon']), area_m2=area(to_tuple(state['polygon'])), mec_radius_m=r)
        if methods is None:
            witness=radius_lower_witness(to_tuple(state['polygon']))
            assert witness['radius_lower_bound_m']>R+1e-7
            for arm in ('mec_center','inner_safe_disk','full_K_nearest','full_K_route'):
                rows.append(dict(**common,arm=arm,single_clear_feasible=False, certified=False,
                    entry_distance_m=None, entry_exit_distance_m=None, maximum_vertex_distance_m=None,
                    geometry_runtime_ms=None, empty_K_radius_lower_bound_m=witness['radius_lower_bound_m'],
                    decision='K(P) empty: do not execute one certified clear'))
            details.append(dict(state_id=state['state_id'],empty_K_certificate=witness))
            continue
        times={key:[] for key in methods}; points={}
        names=list(methods)
        for repeat in range(7):
            for arm in names[repeat%4:]+names[:repeat%4]:
                started=time.perf_counter_ns(); q=methods[arm](); elapsed=(time.perf_counter_ns()-started)/1e6
                points[arm]=q;times[arm].append(elapsed)
        local={}
        for arm,q in points.items():
            maximum=max(math.dist(q,v) for v in state['polygon'])
            assert maximum<=R+2e-7,(state['state_id'],arm,maximum)
            entry=math.dist(state['position'],q)
            exit_d=math.dist(q,state['successor']) if state.get('successor') is not None else 0.
            local[arm]=(entry,entry+exit_d)
            rows.append(dict(**common,arm=arm,single_clear_feasible=True,certified=True,
                entry_distance_m=entry,entry_exit_distance_m=entry+exit_d,
                maximum_vertex_distance_m=maximum,safety_margin_m=R-maximum,
                geometry_runtime_ms=statistics.median(times[arm]),
                geometry_runtime_min_ms=min(times[arm]),geometry_runtime_max_ms=max(times[arm]),
                route_complexity_fallback=(arm=='full_K_route' and len(state['polygon'])>32),
                nearest_complexity_fallback=(arm=='full_K_nearest' and len(state['polygon'])>64)))
        assert local['full_K_nearest'][0]<=local['inner_safe_disk'][0]+2e-6
        assert local['full_K_route'][1]<=local['inner_safe_disk'][1]+2e-6
        details.append(dict(state_id=state['state_id'],center=c,radius=r,points=points,timing_repetitions_ms=times))
    return rows,details


def nearest_order(position, points):
    remaining=list(range(len(points))); order=[]; p=position
    while remaining:
        j=min(remaining,key=lambda k:(math.dist(p,points[k]),points[k],k))
        remaining.remove(j);order.append(j);p=points[j]
    return order


def voronoi_certificate(G, poly, points):
    """Exact-form continuous union certificate, evaluated with explicit float tolerance.

    Nearest-site Voronoi cells partition the plane. Intersecting each with P
    gives convex cells. max distance on each cell occurs at a vertex.
    """
    if not points:
        return dict(continuous_covered=False,cells=[],maximum_distance_m=None)
    anchor=poly[0]
    pp=[(p[0]-anchor[0],p[1]-anchor[1]) for p in poly]
    qq=[(q[0]-anchor[0],q[1]-anchor[1]) for q in points]
    cells=[]; maximum=0.; total_area=0.
    for i,q in enumerate(qq):
        cell=pp[:]
        for j,z in enumerate(qq):
            if i==j or math.dist(q,z)<1e-10:
                continue
            cell=G._sp_clip(cell,2*(z[0]-q[0]),2*(z[1]-q[1]),z[0]**2+z[1]**2-q[0]**2-q[1]**2)
            if not cell:break
        if not cell:continue
        distance=max(math.dist(q,v) for v in cell)
        maximum=max(maximum,distance);total_area+=area(cell)
        cells.append(dict(disk_index=i,vertices=[(v[0]+anchor[0],v[1]+anchor[1]) for v in cell],
            maximum_vertex_distance_m=distance,area_m2=area(cell)))
    p_area=area(pp)
    area_gap=abs(total_area-p_area)
    return dict(continuous_covered=maximum<=R+2e-7 and area_gap<=max(1e-5,p_area*1e-8),
        method='nearest-centre Voronoi cells plus all-vertex containment; no coverage sampling',
        maximum_distance_m=maximum,polygon_area_m2=p_area,sum_voronoi_cell_area_m2=total_area,
        area_gap_m2=area_gap,cells=cells,floating_tolerance_m=2e-7)


def grid_plan(G,state):
    poly=to_tuple(state['polygon']);origin=state.get('grid_origin',(0.,0.));a=math.radians(state.get('grid_angle_deg',0.))
    u=(math.cos(a),math.sin(a));v=(-u[1],u[0]);spacing=25.
    local=[((p[0]-origin[0])*u[0]+(p[1]-origin[1])*u[1],
            (p[0]-origin[0])*v[0]+(p[1]-origin[1])*v[1]) for p in poly]
    lo=[math.floor((min(p[d] for p in local)-spacing/2)/spacing) for d in (0,1)]
    hi=[math.ceil((max(p[d] for p in local)+spacing/2)/spacing) for d in (0,1)]
    cells=[];points=[]
    for i in range(lo[0],hi[0]+1):
        for j in range(lo[1],hi[1]+1):
            cell=local
            for a,b,c in [(1,0,(i+.5)*spacing),(-1,0,(-i+.5)*spacing),(0,1,(j+.5)*spacing),(0,-1,(-j+.5)*spacing)]:
                cell=G._sp_clip(cell,a,b,c)
            if not cell:continue
            point=(origin[0]+i*spacing*u[0]+j*spacing*v[0],origin[1]+i*spacing*u[1]+j*spacing*v[1])
            world_cell=[(origin[0]+p[0]*u[0]+p[1]*v[0],origin[1]+p[0]*u[1]+p[1]*v[1]) for p in cell]
            points.append(point);cells.append(world_cell)
    return dict(points=points,cells=cells,construction='25m rotated square grid',
                partition_proof='All 25m square cells intersecting P retained; square circumradius 25/sqrt(2)<20')


def strip_cells(G,poly,u,fractions):
    values=[u[0]*p[0]+u[1]*p[1] for p in poly];lo,hi=min(values),max(values)
    boundaries=[lo]+[lo+(hi-lo)*f for f in fractions]+[hi]
    cells=[]
    for left,right in zip(boundaries,boundaries[1:]):
        cell=G._sp_clip(G._sp_clip(poly,-u[0],-u[1],-left),u[0],u[1],right)
        if not cell:return [],[]
        cells.append(cell)
    return cells,boundaries


def adaptive_plan(G,state):
    poly=to_tuple(state['polygon']);c,r=G._sp_enclosing_circle(poly)
    if r<=R-1e-5:
        return dict(points=[c],cells=[poly],construction='single certified circle',partition_proof='P itself')
    a,b=max(itertools.combinations(poly,2),key=lambda pair:math.dist(*pair))
    d=math.dist(a,b);u=((b[0]-a[0])/d,(b[1]-a[1])/d)
    choices=[]
    fraction_sets=[(f,) for f in (.35,.425,.5,.575,.65)]
    fraction_sets += [(1/3,2/3),(.3,.65),(.35,.7)]
    fraction_sets += [tuple(k/n for k in range(1,n)) for n in range(4,11)]
    for fractions in fraction_sets:
        cells,bounds=strip_cells(G,poly,u,fractions)
        if not cells:continue
        circles=[G._sp_enclosing_circle(cell) for cell in cells]
        if any(rr>R-1e-5 for cc,rr in circles):continue
        points=[cc for cc,rr in circles];order=nearest_order(state['position'],points)
        seq=[points[i] for i in order]
        length=math.dist(state['position'],seq[0])+sum(math.dist(x,y) for x,y in zip(seq,seq[1:]))
        choices.append((len(points),length,points,cells,bounds))
    if choices:
        _,_,points,cells,bounds=min(choices,key=lambda x:(x[0],x[1],x[2]))
        return dict(points=points,cells=cells,construction='B3-compatible finite strip geometry without cost gate or standoff',
            partition_proof='Contiguous projection intervals span [min projection,max projection]',axis=u,boundaries=bounds)
    # Explicit new geometry extension, not claimed to be implemented in B3.
    leaves=[];splits=[]
    def split(cell,depth=0):
        cc,rr=G._sp_enclosing_circle(cell)
        if rr<=R-1e-5:
            leaves.append((cc,cell));return
        assert depth<20 and len(leaves)<128,'Recursive partition exceeded registered safety guard'
        aa,bb=max(itertools.combinations(cell,2),key=lambda pair:math.dist(*pair));dd=math.dist(aa,bb)
        axis=((bb[0]-aa[0])/dd,(bb[1]-aa[1])/dd)
        parts,bounds=strip_cells(G,cell,axis,(.5,))
        assert len(parts)==2
        splits.append(dict(axis=axis,boundary=bounds[1],depth=depth,parent=cell))
        for part in parts:split(part,depth+1)
    split(poly)
    return dict(points=[q for q,cell in leaves],cells=[cell for q,cell in leaves],
        construction='recursive convex partition extension (not current B3)',
        partition_proof='Every binary split retains both closed half-plane children',splits=splits)


def planning_atoms(G,poly,count=243):
    return G._DecisionSpatial.belief_quadrature(None,poly,count)


def sequence_metrics(position,points,atoms):
    length=math.dist(position,points[0])+sum(math.dist(a,b) for a,b in zip(points,points[1:]))
    costs=[];distances=[];attempts=[]
    for target in atoms:
        p=position;distance=0.
        for k,q in enumerate(points,1):
            distance+=math.dist(p,q);p=q
            if math.dist(q,target)<=R+1e-8:
                costs.append(distance/5.+3.*k+2.);distances.append(distance);attempts.append(k);break
        else:raise AssertionError('A planning atom is not covered despite a continuous certificate')
    return dict(circle_count=len(points),entire_plan_distance_m=length,
        exhaustive_success_cost_upper_s=length/5.+3.*len(points)+2.,
        equal_area_planning_first_hit_cost_s=statistics.mean(costs),
        equal_area_planning_first_hit_distance_m=statistics.mean(distances),
        equal_area_planning_first_hit_attempts=statistics.mean(attempts),
        planning_atom_count=len(atoms),clear_action_cost_model='distance/5 + 3*attempts + 2',
        planning_distribution_is_official=False)


def bearing_proxy(module,state,atoms):
    poly=to_tuple(state['polygon']);center,radius=module._G._sp_enclosing_circle(poly)
    if radius<=R+1e-8:
        # A continue-until-single-disk comparator stops immediately when its
        # own stopping condition already holds; do not charge an extra measure.
        direct=math.dist(state['position'],center)/5.+5.
        return dict(measure_point=None,additional_measure_count=0,measurement_move_m=0.,measurement_cost_s=0.,
            zero_added_error_planning_single_disk_fraction=1.,zero_added_error_planning_near_fraction=None,
            mean_predicted_radius_m=radius,max_sampled_predicted_radius_m=radius,
            assumed_one_measure_then_center_clear_proxy_s=direct,guaranteed_complete_policy=True,
            continuous_covered=True,boundary='P already fits one 20m disk: stop measuring and clear at its certified centre.')
    measurement=center;move=math.dist(state['position'],measurement)
    predicted=[];costs=[];certified=0;near=0
    for target in atoms:
        if math.dist(target,measurement)<=5.:
            rho=5.;estimate=measurement;near+=1
        else:
            angle=math.atan2(target[1]-measurement[1],target[0]-measurement[0])
            posterior=module._wedge(poly,measurement,angle)
            estimate,rho=module._G._sp_enclosing_circle(posterior)
        certified+=rho<=R+1e-8;predicted.append(rho)
        costs.append(move/5.+5.+math.dist(measurement,estimate)/5.+5.)
    return dict(measure_point=measurement,additional_measure_count=1,
        measurement_move_m=move,measurement_cost_s=move/5.+5.,
        zero_added_error_planning_single_disk_fraction=certified/len(atoms),
        zero_added_error_planning_near_fraction=near/len(atoms),
        mean_predicted_radius_m=statistics.mean(predicted),max_sampled_predicted_radius_m=max(predicted),
        assumed_one_measure_then_center_clear_proxy_s=statistics.mean(costs),
        guaranteed_complete_policy=False,continuous_covered=None,
        boundary='Zero-added-error one-step bearing model; Q4 reception not guaranteed; final clear cost assumes success. Not a task-time result.')


class NoActions:
    def _forbid(self,*args,**kwargs):
        raise RuntimeError('State-only planner attempted an environment action')
    enter=measure=clear=exit=_forbid


def native_b3_plan(module,state):
    solver=module.Solver(NoActions(),mode=state['mode']);ch=1
    solver.position=tuple(state['position']);solver.polygons[ch]=to_tuple(state['polygon'])
    solver.observations[ch]=[(tuple(p),d) for p,d in state.get('observations',[])]
    solver.no_signal_points[ch]=[tuple(p) for p in state.get('no_signal_points',[])]
    if hasattr(solver,'failed_clear_points'):
        solver.failed_clear_points[ch]=[tuple(p) for p in state.get('failed_clear_points',[])]
    if hasattr(solver,'_e2_failed_clear'):
        solver._e2_failed_clear[ch]=[tuple(p) for p in state.get('failed_clear_points',[])]
    solver._active_target=ch
    started=time.perf_counter_ns();plan=solver._three_disk_plan(ch);elapsed=(time.perf_counter_ns()-started)/1e6
    return plan,elapsed


def run_coverage_states(module,states):
    G=module._G;rows=[];details=[];native=[]
    for index,state in enumerate(states):
        poly=to_tuple(state['polygon']);center,radius=G._sp_enclosing_circle(poly);atoms=planning_atoms(G,poly)
        common=dict(state_id=state['state_id'],evidence=state['evidence'],family=state['family'],mode=state['mode'],
            vertices=len(poly),area_m2=area(poly),mec_radius_m=radius)
        for arm,builder in [('grid25_nearest_order',grid_plan),('adaptive_certified_partition_nearest_order',adaptive_plan)]:
            times=[];plan=None
            for _ in range(3):
                started=time.perf_counter_ns();plan=builder(G,state);times.append((time.perf_counter_ns()-started)/1e6)
            for q,cell in zip(plan['points'],plan['cells']):
                assert max(math.dist(q,v) for v in cell)<=R+2e-7
            order=nearest_order(state['position'],plan['points']);points=[plan['points'][j] for j in order]
            cert=voronoi_certificate(G,poly,points)
            assert cert['continuous_covered'],(state['state_id'],arm,cert['maximum_distance_m'])
            rows.append(dict(**common,arm=arm,continuous_covered=True,
                construction=plan['construction'],maximum_voronoi_vertex_distance_m=cert['maximum_distance_m'],
                geometry_runtime_ms=statistics.median(times),**sequence_metrics(state['position'],points,atoms)))
            details.append(dict(state_id=state['state_id'],arm=arm,construction=plan,visit_order=order,
                                ordered_points=points,independent_union_certificate=cert,timing_repetitions_ms=times))
        started=time.perf_counter_ns();proxy=bearing_proxy(module,state,atoms);elapsed=(time.perf_counter_ns()-started)/1e6
        rows.append(dict(**common,arm='continue_bearing_one_step_proxy',geometry_runtime_ms=elapsed,**proxy))
        plan,elapsed=native_b3_plan(module,state)
        if plan:
            cert=voronoi_certificate(G,poly,list(plan));assert cert['continuous_covered']
            native.append(dict(**common,plan_returned=True,native_geometry_runtime_ms=elapsed,
                continuous_covered=True,maximum_voronoi_vertex_distance_m=cert['maximum_distance_m'],
                **sequence_metrics(state['position'],list(plan),atoms)))
            details.append(dict(state_id=state['state_id'],arm='unchanged_B3_optional_plan',ordered_points=plan,
                                independent_union_certificate=cert))
        else:
            native.append(dict(**common,plan_returned=False,native_geometry_runtime_ms=elapsed,
                continuous_covered=None,boundary='No optional plan returned; B3 retains measuring and fallback. This is not a clearing failure.'))
        if (index+1)%10==0:print(f'coverage states completed: {index+1}/{len(states)}',flush=True)
    return rows,details,native


def analytic_checks():
    spindle=[(0.,-6.),(30.,-12.),(60.,-6.),(60.,6.),(30.,12.),(0.,6.)]
    radius_sq=15.**2+12.**2
    left=[(0.,-6.),(30.,-12.),(30.,12.),(0.,6.)]
    right=[(30.,-12.),(60.,-6.),(60.,6.),(30.,12.)]
    assert all((v[0]-c[0])**2+(v[1]-c[1])**2<=radius_sq for c,cell in [((15.,0.),left),((45.,0.),right)] for v in cell)
    q=(100.-math.sqrt(175.),0.)
    return dict(evidence='analytic_constructed_check',not_simulation=True,
        spindle=dict(polygon=spindle,centers=[(15.,0.),(45.,0.)],cells=[left,right],
            squared_radius_upper=369,clear_radius_squared=400,certified=True,
            minimum_circle_count=2,minimality_proof='P contains points (0,6) and (60,6) at distance 60>40; one 20m disk is impossible; two certified cells attain two.'),
        action_segment=dict(polygon=[(100.,-15.),(100.,15.)],position=(0.,0.),mec_center=(100.,0.),
            full_K_nearest=q,center_distance_m=100.,inner_disk_distance_m=95.,full_K_distance_m=q[0],
            saved_vs_center_m=100.-q[0],saved_vs_inner_disk_m=95.-q[0],
            proof='For both endpoints: (100-q_x)^2+15^2=175+225=400; convexity covers the full segment.'),
        numerical_tests_do_not_replace_proofs=True)


def summarize(action_rows,coverage_rows,native_rows,replay_audit):
    summary=dict(evidence_boundary='Synthetic constructed states only in this run; zero new worlds, no public trace replay, no official execution, no blind evaluation.',
        new_world_executions=0,public_trace_replays=len(replay_audit),
        public_actions_replayed=sum(x['matched_actions'] for x in replay_audit),
        replay_actions_match=all(x['complete_trace_consumed'] and x['max_coordinate_delta_m']<1e-7 for x in replay_audit) if replay_audit else None,
        public_replay_status='completed' if replay_audit else 'not executed: synthetic scope fixed by coordinator before run',
        action={},coverage={},native_b3={})
    for evidence in ('synthetic_state_mechanism','replayed_public_state_mechanism'):
        ar=[x for x in action_rows if x['evidence']==evidence]
        by={}
        for x in ar:by.setdefault(x['state_id'],{})[x['arm']]=x
        valid=[v for v in by.values() if v['mec_center']['single_clear_feasible']]
        summary['action'][evidence]=dict(states=len(by),feasible_single_clear_states=len(valid),
            correctly_rejected_empty_K_states=len(by)-len(valid),all_returned_points_certified=all(x['certified'] for x in ar if x['single_clear_feasible']),
            mean_entry_saved_K_nearest_vs_center_m=statistics.mean(v['mec_center']['entry_distance_m']-v['full_K_nearest']['entry_distance_m'] for v in valid) if valid else None,
            mean_entry_saved_K_nearest_vs_inner_m=statistics.mean(v['inner_safe_disk']['entry_distance_m']-v['full_K_nearest']['entry_distance_m'] for v in valid) if valid else None,
            mean_route_saved_K_route_vs_center_m=statistics.mean(v['mec_center']['entry_exit_distance_m']-v['full_K_route']['entry_exit_distance_m'] for v in valid) if valid else None,
            mean_route_saved_K_route_vs_inner_m=statistics.mean(v['inner_safe_disk']['entry_exit_distance_m']-v['full_K_route']['entry_exit_distance_m'] for v in valid) if valid else None,
            timing_median_ms_by_arm={arm:statistics.median(x['geometry_runtime_ms'] for x in ar if x['arm']==arm and x['single_clear_feasible']) for arm in ('mec_center','inner_safe_disk','full_K_nearest','full_K_route')} if valid else {})
        cr=[x for x in coverage_rows if x['evidence']==evidence];b={}
        for x in cr:b.setdefault(x['state_id'],{})[x['arm']]=x
        pairs=list(b.values());grid='grid25_nearest_order';adapt='adaptive_certified_partition_nearest_order'
        summary['coverage'][evidence]=dict(states=len(pairs),all_optical_plans_continuously_covered=all(x['continuous_covered'] for x in cr if x['arm']!= 'continue_bearing_one_step_proxy'),
            mean_grid_disks=statistics.mean(x[grid]['circle_count'] for x in pairs) if pairs else None,
            mean_adaptive_disks=statistics.mean(x[adapt]['circle_count'] for x in pairs) if pairs else None,
            adaptive_fewer_disks=sum(x[adapt]['circle_count']<x[grid]['circle_count'] for x in pairs),
            adaptive_more_disks=sum(x[adapt]['circle_count']>x[grid]['circle_count'] for x in pairs),
            native_compatible_strip_states=sum('extension' not in x[adapt]['construction'] for x in pairs),
            recursive_extension_states=sum('extension' in x[adapt]['construction'] for x in pairs),
            mean_grid_exhaustive_cost_upper_s=statistics.mean(x[grid]['exhaustive_success_cost_upper_s'] for x in pairs) if pairs else None,
            mean_adaptive_exhaustive_cost_upper_s=statistics.mean(x[adapt]['exhaustive_success_cost_upper_s'] for x in pairs) if pairs else None,
            mean_grid_equal_area_planning_cost_s=statistics.mean(x[grid]['equal_area_planning_first_hit_cost_s'] for x in pairs) if pairs else None,
            mean_adaptive_equal_area_planning_cost_s=statistics.mean(x[adapt]['equal_area_planning_first_hit_cost_s'] for x in pairs) if pairs else None,
            adaptive_planning_cost_better=sum(x[adapt]['equal_area_planning_first_hit_cost_s']<x[grid]['equal_area_planning_first_hit_cost_s']-1e-7 for x in pairs),
            adaptive_planning_cost_worse=sum(x[adapt]['equal_area_planning_first_hit_cost_s']>x[grid]['equal_area_planning_first_hit_cost_s']+1e-7 for x in pairs))
        nr=[x for x in native_rows if x['evidence']==evidence]
        summary['native_b3'][evidence]=dict(states=len(nr),optional_plans_returned=sum(x['plan_returned'] for x in nr),
            all_returned_plans_continuously_covered=all(x['continuous_covered'] for x in nr if x['plan_returned']))
    return summary


def run(out,reg):
    if out.exists():raise FileExistsError(f'Output exists: {out}; choose a fresh --out directory')
    out.mkdir(parents=True)
    started=time.time();module,matches=load_solver(reg)
    dump(out/'registration.json',reg);dump(out/'embedded_source_matches.json',matches)
    inputs=[HERE/'registration.json',HERE/'run_experiments.py',Path(__file__),CODE/reg['source_solver'],CODE/'evaluation/manifest_v1.json']
    manifest={str(p.relative_to(CODE)):sha(p) for p in inputs}
    dump(out/'input_manifest.json',dict(sha256=manifest,python=sys.version,platform=platform.platform(),
        command_arguments=[sys.executable,'-S',str(HERE / 'run_experiments.py'),'--out',str(out)],external_packages_required=[]))
    synthetic_coverage,synthetic_actions=build_synthetic(module._G,reg)
    # Scope narrowed by coordinator before execution: public replay is an
    # optional future extension; synthetic results must not depend on it.
    public_coverage,public_actions,replay_audit=[],[],[]
    dump(out/'public_replay_audit.json',replay_audit)
    dump(out/'synthetic_coverage_states.json',synthetic_coverage);dump(out/'synthetic_action_states.json',synthetic_actions)
    dump(out/'public_coverage_states.json',public_coverage);dump(out/'public_action_states.json',public_actions)
    dump(out/'analytic_checks.json',analytic_checks())
    print(f'Public replay matched: {len(replay_audit)} traces. States: {len(public_coverage)} coverage, {len(public_actions)} action.',flush=True)
    action_rows,action_details=run_action_states(module._G,synthetic_actions+public_actions)
    dump(out/'action_rows.json',action_rows);write_csv(out/'action_rows.csv',action_rows);dump(out/'action_details.json',action_details)
    interim=summarize(action_rows,[],[],replay_audit);dump(out/'action_summary.json',interim['action'])
    print('Highlight 3 complete: action_rows.json, action_rows.csv, action_summary.json',flush=True)
    coverage_rows,coverage_details,native_rows=run_coverage_states(module,synthetic_coverage+public_coverage)
    dump(out/'coverage_rows.json',coverage_rows);write_csv(out/'coverage_rows.csv',coverage_rows)
    dump(out/'coverage_certificates.json',coverage_details);dump(out/'native_b3_rows.json',native_rows);write_csv(out/'native_b3_rows.csv',native_rows)
    summary=summarize(action_rows,coverage_rows,native_rows,replay_audit)
    summary['wall_time_s']=time.time()-started
    summary['input_files_unchanged']=all(sha(CODE/p)==h for p,h in manifest.items())
    assert summary['input_files_unchanged']
    dump(out/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
