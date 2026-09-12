"""Nine registered source operations generated only from detached public state."""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import math
from pathlib import Path
from . import vendor
from .state import (canonical_json, controller_state, decode, digest, encode,
                    restore_controller, validate_controller_state, validate_engine_state, point)

GENERATOR_VERSION = 'bc-rpi-q4-source-operations-v1'


def source_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def coordinate(value):
    if not math.isfinite(value):
        raise ValueError('Nonfinite candidate coordinate')
    d = Decimal(str(float(value))).quantize(Decimal('0.0000001'), rounding=ROUND_HALF_EVEN)
    return format(abs(d) if d == 0 else d, '.7f')


def base_payload(meta, kind, channel, target, labels, certified=False):
    payload = dict(kind=kind, channel=channel, target=target,
        labels=sorted(labels), certified_before_action=bool(certified),
        pre_state_hash=meta['pre_state_hash'], prepared_state_hash=meta['prepared_state_hash'],
        controller_patch_hash=meta['controller_patch_hash'], route_successor=meta['route_successor'],
        operation_implementation_sha256=vendor.implementation_hash(),
        next_boundary='READY_PREPARE', budget_cost_slots=int(kind != 'teacher_service'),
        generator_version=GENERATOR_VERSION)
    return payload


def generate(public):
    required = {'controller', 'engine', 'meta'}
    if set(public) != required:
        raise ValueError('Candidate input whitelist violated')
    values, state, meta = decode(public['controller']), decode(public['engine']), public['meta']
    validate_controller_state(values)
    validate_engine_state(state)
    if set(meta) != {'pre_state_hash','prepared_state_hash','controller_patch_hash','route_successor','teacher_task'}:
        raise ValueError('Unregistered candidate metadata fields')
    if set(meta['teacher_task']) != {'kind','key','defer'}:
        raise ValueError('Unregistered teacher-task fields')
    for name in ('pre_state_hash','prepared_state_hash','controller_patch_hash'):
        if type(meta[name]) is not str or len(meta[name])!=64 or any(x not in '0123456789abcdef' for x in meta[name]):
            raise ValueError('Invalid candidate metadata hash')
    if meta['route_successor'] is not None and not point(meta['route_successor']):
        raise ValueError('Invalid candidate route successor')
    task=meta['teacher_task']
    if (task['kind']!='source' or type(task['key']) is not int or not 1<=task['key']<=20
            or type(task['defer']) is not bool):
        raise ValueError('Invalid source teacher-task values')
    mode = values['mode']
    s = restore_controller(vendor.NoCalls(), mode, values)
    task = meta['teacher_task']
    if task['kind'] != 'source':
        raise ValueError('Only source choices enter operation generator')
    ch = task['key']
    c, r = vendor.engine._circle(s, s.polygons[ch])
    teacher = base_payload(meta, 'teacher_service', ch, list(c), ['A0'])
    teacher['budget_cost_slots'] = 0
    teacher['service_state'] = encode({name: getattr(s, name, {}).get(ch) for name in
        ('_e2_progress', '_e2_failed_clear', 'failed_clear_points')})
    teacher['original_localize_source_sha256'] = vendor.C7_SHA256
    teacher_id = digest(teacher)
    items = [(teacher_id, teacher)]
    reasons = []
    b = state.get('interventions_remaining')
    eligible = (mode == 4 and type(b) is int and 0 < b <= 2 and ch not in state['forced_teacher_channels']
        and bool(s.observations[ch]) and ch not in s.cleared
        and s.config.get('e2_same_here') is False
        and getattr(s, '_active_target', None) is None and getattr(s, '_sharing', False) is False
        and len(s.polygons[ch]) >= 3 and math.isfinite(r)
        and all(math.isfinite(v) for point in s.polygons[ch] for v in point))
    if not eligible:
        reasons.append('not_eligible')
    alternatives = {}
    if eligible:
        p = s.position
        p_last, bearing = s.observations[ch][-1]
        angle = math.radians(bearing)
        u = (math.cos(angle), math.sin(angle))
        v = (-u[1], u[0])
        ell = min(120., max(25., 0.15 * r))
        known_measure_points = [old for old, _ in s.observations[ch]] + list(s.no_signal_points[ch])
        known_canonical = {(coordinate(q[0]), coordinate(q[1])) for q in known_measure_points}

        def add(label, kind, target):
            xy = (coordinate(target[0]), coordinate(target[1]))
            q = tuple(float(x) for x in xy)
            if not all(abs(x) <= 4000 for x in q):
                reasons.append(label + ':outside_box')
                return
            if label == 'A3' and xy in known_canonical:
                reasons.append(label + ':known_measure_position')
                return
            certified = kind == 'clear_override' and all(math.dist(q, z) <= 20. - 1e-6 for z in s.polygons[ch])
            key = (kind, ch, *xy)
            if key not in alternatives:
                alternatives[key] = base_payload(meta, kind, ch, list(xy), [label], certified)
            else:
                alternatives[key]['labels'].append(label)
                alternatives[key]['labels'].sort()

        if r <= 300:
            add('A1', 'clear_override', c)
            grid = s.optical_points(ch)
            if grid:
                add('A2', 'clear_override', min(grid, key=lambda q: (math.dist(p, q), q)))
        add('A3', 'measure_override', c)
        q = s.second_point(ch)
        add('A4', 'measure_override', q)
        delta = (q[0] - p_last[0], q[1] - p_last[1])
        dot_u = sum(a*b for a, b in zip(delta, u))
        dot_v = sum(a*b for a, b in zip(delta, v))
        add('A5', 'measure_override', tuple(p_last[i] + dot_u*u[i] - dot_v*v[i] for i in range(2)))
        add('A6', 'measure_override', tuple((p[i] + p_last[i]) / 2 for i in range(2)))
        add('A7', 'measure_override', tuple(c[i] + ell*v[i] for i in range(2)))
        add('A8', 'measure_override', tuple(c[i] - ell*v[i] for i in range(2)))
        items += [(digest(payload), payload) for payload in alternatives.values()]
    items.sort(key=lambda item: item[0])
    if len(items) > 9 or len({key for key, _ in items}) != len(items):
        raise ValueError('Candidate count or identity invariant')
    result = dict(schema='bc-rpi-choice-v1', generator_sha256=source_hash(),
        teacher_id=teacher_id, candidate_ids=[key for key, _ in items],
        candidates=[payload for _, payload in items], eligible=eligible, rejections=reasons)
    result['features'] = features(values, state, result)
    return result


def features(values, state, choices):
    """Exact 20/20x12/Lx14/32x2/Kx14 public tensor contract; no weights."""
    s = restore_controller(vendor.NoCalls(), values['mode'], values)
    ch = next(p['channel'] for p in choices['candidates'] if p['kind'] == 'teacher_service')
    theta = math.radians(s.observations[ch][0][1])
    cs, sn = math.cos(theta), math.sin(theta)
    p = s.position

    def xy(q):
        dx, dy = q[0]-p[0], q[1]-p[1]
        return [(cs*dx+sn*dy)/1800, (-sn*dx+cs*dy)/1800]

    def summary(channel):
        poly = s.polygons.get(channel)
        return (vendor.engine._circle(s, poly) + (vendor.geometry.polygon_area(poly),)
                if poly else ((0., 0.), 1800., math.pi*1800**2))

    c, r, area = summary(ch)
    known = s.cleared | {k for k in range(1,21) if s.observations[k]}
    successor = getattr(s, 'route_successor', None)
    global_values = [s.virtual_time/360000, state['previous_macro_seconds']/10000,
        len(s.cleared)/20, len(known)/20, (20-len(known))/20, len(state['todo'])/49,
        state['interventions_remaining']/2, float(ch==s.channel),
        getattr(s, '_e2_progress', {}).get(ch, 0)/9,
        # Target-domain center and active feasible-polygon center are distinct.
        float(ch in state['forced_teacher_channels']), *xy((0., 0.)),
        *(xy(successor) if successor is not None else [0.,0.]), float(successor is not None),
        r/1800, area/(math.pi*1800**2), *xy(c), len(choices['candidates'])/9]
    channels = []
    for channel in range(1,21):
        center, radius, poly_area = summary(channel)
        failed = getattr(s, '_e2_failed_clear', {}).get(channel, []) if s.mode == 4 else getattr(s, 'failed_clear_points', {}).get(channel, [])
        channels.append([float(channel in s.cleared), float(bool(s.observations[channel])),
            len(s.observations[channel])/64, len(s.no_signal_points[channel])/64, len(failed)/64,
            len(s.scanned[channel])/len(s.points), *xy(center), radius/1800,
            poly_area/(math.pi*1800**2), float(channel==ch), float(channel==s.channel)])
    active = []
    previous_position = None
    first_positive_index = None
    kinds = ('direction','near','no_signal','clear_fail','clear_success')
    previous_end = 0.
    for event in s.trace:
        event_end = float(event['virtual_time_s'])
        delta = event_end - previous_end
        previous_end = event_end
        if event['channel'] != ch:
            continue
        kind = event['result'] if event['action']=='measure' else ('clear_success' if event['result']=='success' else 'clear_fail')
        location = (event['x'], event['y'])
        has_bearing = kind == 'direction'
        age = s.virtual_time - event_end
        if age < -1e-7:
            raise ValueError('Future event')
        if has_bearing and first_positive_index is None:
            first_positive_index = len(active)
        relative = math.radians(event['svd_deg']) - theta if has_bearing else 0.
        active.append([*[float(kind==k) for k in kinds], *xy(location),
            math.sin(relative) if has_bearing else 0., math.cos(relative) if has_bearing else 0.,
            float(has_bearing), max(0.,age)/10000,
            float(previous_position==location), delta/2300,
            float(has_bearing and first_positive_index==len(active))])
        previous_position = location
    indexes = set(range(max(0,len(active)-127),len(active)))
    if first_positive_index is not None:
        indexes.add(first_positive_index)
    active_values = [active[i] for i in sorted(indexes)]
    poly = s.polygons[ch]
    edges = [(a,b,math.dist(a,b)) for a,b in zip(poly,poly[1:]+poly[:1])]
    perimeter = sum(length for _,_,length in edges)
    if len(poly)<3 or perimeter<=0:
        raise ValueError('Invalid network polygon')
    polygon_values = []
    for k in range(32):
        remaining = perimeter*k/32
        for a,b,length in edges:
            if remaining <= length and length > 0:
                polygon_values.append(xy(tuple(a[i]+remaining/length*(b[i]-a[i]) for i in range(2))))
                break
            remaining -= length
        else:
            polygon_values.append(xy(poly[-1]))
    action_values = []
    past = [old for old,_ in s.observations[ch]] + list(s.no_signal_points[ch])
    for operation in choices['candidates']:
        q = tuple(float(x) for x in operation['target'])
        kind = operation['kind']
        teacher, measure, clear = kind=='teacher_service', kind=='measure_override', kind=='clear_override'
        move = math.dist(p,q)
        change = int(ch!=s.channel) if measure else 0
        low = move/5 + (5+change if measure or teacher else 3)
        high = low + (5 if measure else 2 if clear else 0)
        visibility = s.predicted_visibility(ch,q) if s.mode==4 else 1.
        action_values.append([float(teacher),float(measure),float(clear),*xy(q),move/8000,
            float(change),low/10000,high/10000,math.dist(q,c)/1800,
            float(operation['certified_before_action']),float(any(q==old for old in past)),
            visibility,float(teacher)])
    result = dict(global_features=global_values, channels=channels, active_events=active_values,
        active_mask=[True]*len(active_values), polygon=polygon_values, actions=action_values,
        events_dropped=len(active)-len(active_values))
    if len(global_values)!=20 or any(len(row)!=12 for row in channels) or any(len(row)!=14 for row in active_values+action_values):
        raise ValueError('Feature dimension mismatch')
    if not all(math.isfinite(v) for row in [global_values,*channels,*active_values,*polygon_values,*action_values] for v in row):
        raise ValueError('Nonfinite public feature')
    return result
