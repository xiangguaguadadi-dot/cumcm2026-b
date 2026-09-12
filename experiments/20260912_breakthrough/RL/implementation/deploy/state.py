"""Lossless JSON public-state encoding and pre-prepare resume tokens."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
import hashlib
import json
import math
from . import vendor


def encode(value):
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        return {'@': 'float', 'v': value.hex()}
    if type(value) in (list, tuple, set):
        values = [encode(x) for x in value]
        if type(value) is set:
            values.sort(key=canonical_json)
        return {'@': type(value).__name__, 'v': values}
    if type(value) is dict:
        pairs = [[encode(k), encode(v)] for k, v in value.items()]
        pairs.sort(key=lambda kv: canonical_json(kv[0]))
        return {'@': 'dict', 'v': pairs}
    raise TypeError('Non-public/unsupported state object: ' + type(value).__name__)


def decode(value):
    if not isinstance(value, dict):
        if value is None or type(value) in (bool, int, str):
            return value
        raise TypeError('Unexpected untagged state value')
    if set(value) != {'@', 'v'}:
        raise ValueError('Unknown state encoding fields')
    tag, v = value['@'], value['v']
    if tag == 'float':
        return float.fromhex(v)
    if tag == 'dict':
        return {decode(k): decode(x) for k, x in v}
    if tag in ('list', 'tuple', 'set'):
        items = [decode(x) for x in v]
        return items if tag == 'list' else tuple(items) if tag == 'tuple' else set(items)
    raise ValueError('Unknown state tag')


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


COUNTER_KEYS = frozenset(('budget_fallbacks','clear_attempts','certified_clear_attempts',
    'heuristic_clear_attempts','conditional_changed_first','conditional_proxy_saving_m',
    'conditional_route_calls','convex_negative_area_removed','convex_negative_shrinks',
    'convex_negative_updates','decision_gate_evaluations','decision_gate_fallback',
    'e2_excluded_cells','e2_gate_accepted','e2_gate_evaluations','e2_same_here_clears',
    'e2_service_rounds','e2_station_retests','failed_clear','fallbacks','geometry_budget_skips',
    'lens_calls','lens_proxy_saved_m','localization_moves','measure','mirror_recovery_measures',
    'opportunity_measures','optical_switches','same_location_clears','scan_stations',
    'segment_recovery_measures','stations_removed_after_discovery','stations_waived_after_all_discovered'))
ENGINE_FIELDS = frozenset(('boundary_phase','todo','visited','no_progress','previous_macro_seconds',
    'decision_counter','last_committed_choice_id','interventions_remaining','forced_teacher_channels',
    'used_operation_ids'))


def number(v):
    return type(v) in (int, float) and math.isfinite(v)


def point(v):
    return type(v) in (tuple,list) and len(v)==2 and all(number(x) for x in v)


@lru_cache(maxsize=2)
def controller_schema(mode):
    s = vendor.make_controller(vendor.NoCalls(), mode)
    return (frozenset(s.__dict__) - {'env','deadline'}, deepcopy(s.config), len(s.points))


def validate_controller_state(values):
    """Frozen field-by-field schema; no generic extra string-key dictionaries."""
    if type(values) is not dict or values.get('mode') not in (3,4):
        raise ValueError('Invalid public controller mode/schema')
    fields, config, station_count = controller_schema(values['mode'])
    if not fields <= set(values) or set(values)-fields-{'route_successor'}:
        raise ValueError('Unregistered public controller fields')
    if values['config'] != config:
        raise ValueError('Frozen controller configuration differs')
    if not point(values['position']) or type(values['channel']) is not int or not 1<=values['channel']<=20:
        raise ValueError('Invalid controller physical position/channel')
    if not number(values['virtual_time']) or not number(values['_sharing_spent_s']):
        raise ValueError('Invalid controller time value')
    if values['_active_target'] is not None and not (type(values['_active_target']) is int and 1<=values['_active_target']<=20):
        raise ValueError('Invalid active target')
    if 'route_successor' in values and values['route_successor'] is not None and not point(values['route_successor']):
        raise ValueError('Invalid route successor')
    for field in ('_sharing','_servicing','_e2_servicing'):
        if field in values and type(values[field]) is not bool:
            raise ValueError('Invalid controller flag: '+field)
    if type(values['cleared']) is not set or any(type(c) is not int or not 1<=c<=20 for c in values['cleared']):
        raise ValueError('Invalid cleared-channel set')
    if type(values['points']) is not list or len(values['points'])!=station_count or not all(point(p) for p in values['points']):
        raise ValueError('Invalid public station list')
    for field in ('observations','polygons','scanned','no_signal_points','failed_clear_points','_e2_failed_clear','_e2_progress','_visibility_cache'):
        if field not in values: continue
        mapping=values[field]
        if type(mapping) is not dict or any(type(c) is not int or not 1<=c<=20 for c in mapping):
            raise ValueError('Invalid public channel mapping: '+field)
        if field in ('observations','scanned','no_signal_points','failed_clear_points','_e2_failed_clear') and set(mapping)!=set(range(1,21)):
            raise ValueError('Incomplete channel ledger: '+field)
        for item in mapping.values():
            valid=False
            if field=='observations':
                valid=type(item) is list and all(type(x) in (tuple,list) and len(x)==2 and point(x[0]) and number(x[1]) for x in item)
            elif field=='scanned':
                valid=type(item) is set and all(type(i) is int and 0<=i<station_count for i in item)
            elif field=='_e2_progress': valid=type(item) is int and item>=0
            elif field=='_visibility_cache':
                valid=(type(item) is tuple and len(item)==2 and type(item[0]) is tuple and len(item[0])==2
                    and all(type(n) is int and n>=0 for n in item[0]) and type(item[1]) is list
                    and all(type(h) is tuple and len(h)==5 and point(h[0]) and (h[1] is None or point(h[1]))
                            and all(number(v) for v in h[2:]) for h in item[1]))
            else: valid=type(item) is list and all(point(p) for p in item)
            if not valid: raise ValueError('Invalid nested channel payload: '+field)
    counters=values['counters']
    if type(counters) is not dict or set(counters)-COUNTER_KEYS or not all(number(v) for v in counters.values()):
        raise ValueError('Unregistered controller counter')
    if values.get('e2_decisions',[]) != []:
        raise ValueError('Logging-disabled teacher cannot carry extra decision dictionaries')
    if type(values['trace']) is not list: raise ValueError('Invalid trace container')
    for e in values['trace']:
        common={'action','x','y','channel','result','virtual_time_s'}
        if type(e) is not dict or e.get('action') not in ('measure','clear'):
            raise ValueError('Invalid trace event')
        extra={'svd_deg'} if e['action']=='measure' else {'certified_before_action'}
        if set(e)!=common|extra or not all(number(e[k]) for k in ('x','y','virtual_time_s')):
            raise ValueError('Unregistered trace payload')
        if type(e['channel']) is not int or not 1<=e['channel']<=20:
            raise ValueError('Invalid trace channel')
        if e['action']=='measure':
            if e['result'] not in ('direction','near','no_signal') or not (number(e['svd_deg']) if e['result']=='direction' else e['svd_deg'] is None):
                raise ValueError('Invalid trace measurement')
        elif e['result'] not in ('success','no_target_in_range') or type(e['certified_before_action']) is not bool:
            raise ValueError('Invalid trace clear')


def validate_engine_state(state):
    if type(state) is not dict or set(state)!=ENGINE_FIELDS:
        raise ValueError('Unregistered engine state fields')
    for field in ('todo','forced_teacher_channels'):
        if type(state[field]) is not set or any(type(i) is not int for i in state[field]):
            raise ValueError('Invalid engine integer set')
    if type(state['visited']) is not list or any(type(i) is not int for i in state['visited']):
        raise ValueError('Invalid visited station sequence')
    for field in ('no_progress','decision_counter','interventions_remaining'):
        if type(state[field]) is not int or state[field]<0:
            raise ValueError('Invalid engine counter: '+field)
    if state['interventions_remaining']>2 or not number(state['previous_macro_seconds']):
        raise ValueError('Invalid slot/time schema')
    if state['last_committed_choice_id'] is not None and not (type(state['last_committed_choice_id']) is str and len(state['last_committed_choice_id'])==64):
        raise ValueError('Invalid committed choice ID')
    if type(state['used_operation_ids']) is not list or any(type(x) is not str or len(x)!=64 for x in state['used_operation_ids']):
        raise ValueError('Invalid operation-ID history')
    if state['boundary_phase'] not in ('NOT_ENTERED','READY_PREPARE','COMMITTED','EXECUTING',
            'PARTIAL_OR_UNKNOWN','FALLBACK','EXIT','FAILED_INTERFACE','FAILED_OTHER'):
        raise ValueError('Invalid engine boundary phase')


def controller_state(s):
    state = {k: deepcopy(v) for k, v in s.__dict__.items() if k not in ('env', 'deadline')}
    validate_controller_state(state)
    return state


def restore_controller(api, mode, state):
    validate_controller_state(state)
    s = vendor.make_controller(api, mode)
    # Exact original mutable fields; no stale constructor defaults survive.
    s.__dict__ = deepcopy(state)
    s.env = api
    s.deadline = None
    return s


INTERFACE_FIELDS = frozenset(('position', 'channel', 'virtual_time', 'events', 'cleared',
    'positive_observations', 'started', 'exited', 'phase', 'takeover_reason', 'learning_requests',
    'exit_certificate', 'accounting_max_error_s', '_pending_timing',
    'timing_settled_through_event_count', 'inflight_request', 'unknown_backend_failure'))
INTERFACE_EXCLUDED = frozenset(('_enter', '_measure', '_clear', '_exit', 'guard', 'clock',
    'started_at', 'deadline', '_last_response_at'))


def interface_state(api):
    unknown = set(api.__dict__) - INTERFACE_FIELDS - INTERFACE_EXCLUDED
    missing = INTERFACE_FIELDS - set(api.__dict__)
    if unknown or missing:
        raise ValueError(f'Unregistered interface fields: unknown={unknown}, missing={missing}')
    return {k: deepcopy(getattr(api, k)) for k in INTERFACE_FIELDS}


def canonical_events(events):
    return [dict(index=e['index'], phase=e['phase'], action=e['action'], request=e['request'],
                 response={k: v for k, v in e['response'].items()
                           if k not in ('real_timestamp_ms', 'remaining_real_duration_s')},
                 delta_time_s=e['delta_time_s'], expected_time_s=e['expected_time_s'],
                 accounting_error_s=e['accounting_error_s']) for e in events]


def semantic_interface_state(api):
    data = interface_state(api)
    data['events'] = canonical_events(data['events'])
    data.pop('_pending_timing')  # machine timing only, exact value still in token
    data['guard'] = asdict(api.guard)
    return data


def semantic_state_hash(s, api, engine_state):
    return digest(encode(dict(controller=controller_state(s),
                              interface=semantic_interface_state(api), engine=engine_state)))


@dataclass(frozen=True)
class ResumeToken:
    schema: str
    boundary_phase: str
    teacher_sha256: str
    engine_sha256: str
    generator_sha256: str
    implementation_sha256: str
    controller_public_state: dict
    interface_public_state: dict
    guard: dict
    clock_offsets: dict
    engine_state: dict
    accepted_event_count: int
    prefix_virtual_us: int
    public_ledger_digest: str
    semantic_pre_hash: str
    integrity_sha256: str

    def to_json(self):
        return asdict(self)

    def verify_integrity(self):
        value=self.to_json()
        expected=value.pop('integrity_sha256')
        if digest(value)!=expected:
            raise ValueError('ResumeToken full-payload integrity mismatch')

    @classmethod
    def from_json(cls, value):
        if set(value) != set(cls.__dataclass_fields__):
            raise ValueError('Unknown or missing ResumeToken fields')
        result=cls(**value)
        result.verify_integrity()
        return result


def assert_ready(s, api, engine_state):
    validate_engine_state(engine_state)
    if engine_state['boundary_phase'] != 'READY_PREPARE':
        raise ValueError('Snapshot only at pre-prepare boundary')
    if getattr(s, '_active_target', None) is not None or getattr(s, '_sharing', False):
        raise ValueError('Active nested controller stack')
    if not api.started or api.exited or api.phase != 'learning' or api.takeover_reason is not None:
        raise ValueError('Interface is not at a learning READY state')
    if api.inflight_request is not None or api.timing_settled_through_event_count != len(api.events):
        raise ValueError('Unsettled interface request/timing')
    if api.unknown_backend_failure is not None:
        raise ValueError('Unknown backend acceptance cannot be resumed')
    if s.position != api.position or s.channel != api.channel or s.cleared != api.cleared:
        raise ValueError('Controller and interface physical ledgers disagree')
    if round(s.virtual_time * 1e6) != round(api.virtual_time * 1e6):
        raise ValueError('Controller and interface microsecond ledgers disagree')
    if type(engine_state['interventions_remaining']) is not int or not 0 <= engine_state['interventions_remaining'] <= 2:
        raise ValueError('Invalid intervention slot schema')


def make_token(s, api, engine_state, engine_sha, generator_sha):
    assert_ready(s, api, engine_state)
    now = api.clock()
    offsets = dict(task_elapsed_real_s=max(0., now - api.started_at),
        interface_deadline_remaining_s=api.deadline - now,
        controller_deadline_remaining_s=s.deadline - now if s.deadline is not None else None,
        last_response_age_real_s=max(0., now - api._last_response_at) if api._last_response_at is not None else None)
    result = ResumeToken(schema='bc-rpi-engine-state-v1', boundary_phase='READY_PREPARE',
        teacher_sha256=vendor.C7_SHA256, engine_sha256=engine_sha, generator_sha256=generator_sha,
        implementation_sha256=vendor.implementation_hash(),
        controller_public_state=encode(controller_state(s)), interface_public_state=encode(interface_state(api)),
        guard=asdict(api.guard), clock_offsets=offsets, engine_state=encode(engine_state),
        accepted_event_count=len(api.events), prefix_virtual_us=round(api.virtual_time * 1e6),
        public_ledger_digest=digest(canonical_events(api.events)),
        semantic_pre_hash=semantic_state_hash(s, api, engine_state), integrity_sha256='')
    value=result.to_json()
    value.pop('integrity_sha256')
    return replace(result,integrity_sha256=digest(value))
