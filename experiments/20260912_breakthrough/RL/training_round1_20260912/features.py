"""Observation-only D2 tensors; full public events, never a private fork handle.

The previously accepted geometry/candidate worker supplies global/channel/
polygon/action values. Active history is independently rebuilt from the complete
settled interface event ledger, not a potentially shortened controller trace.
"""
from __future__ import annotations
from copy import deepcopy
import math
from implementation.deploy.state import decode

TENSOR_KEYS={'global_features','channels','active_events','active_mask','polygon','actions'}
RAW_EVENT_KEYS={'accounting_error_s','action','backend_call_s','compute_since_previous_response_s',
    'delta_time_s','expected_time_s','index','phase','request','response'}
RESPONSE_KEYS={'accepted','virtual_time_s','measure_result','clear_result','svd_deg','exit_reason',
    'real_timestamp_ms','remaining_real_duration_s','max_real_duration_s','max_virtual_duration_s'}

def number(value):
    if type(value) not in (float,int) or not math.isfinite(value):raise ValueError('Nonfinite or nonnumeric public value')
    return float(value)

def event_projection(events):
    """Drop all machine-clock/cost-probe fields before feature construction."""
    projected=[];previous_us=0
    for index,event in enumerate(events):
        if type(event) is not dict or set(event)-RAW_EVENT_KEYS:raise ValueError('Unknown public event fields')
        if event['index']!=index:raise ValueError('Public events must be complete, ordered prefix')
        action=event['action'];response=event['response'];request=event['request']
        if action not in ('enter','measure','clear','exit'):raise ValueError('Unknown public action')
        if type(response) is not dict or set(response)-RESPONSE_KEYS:raise ValueError('Unknown response fields')
        if response.get('accepted') is not True:raise ValueError('Unsettled/rejected event in accepted prefix')
        end_us=round(number(response['virtual_time_s'])*1e6)
        delta_us=round(number(event['delta_time_s'])*1e6)
        if min(end_us,delta_us)<0 or end_us-previous_us!=delta_us:raise ValueError('Public event microseconds do not telescope')
        previous_us=end_us
        if action in ('enter','exit'):
            if request!={} or delta_us!=0:raise ValueError('Invalid enter/exit public event')
            continue
        if set(request)!={'channel','position'} or set(request['position'])!={'x','y'}:
            raise ValueError('Unknown coordinate/channel request fields')
        channel=request['channel']
        if type(channel) is not int or not 1<=channel<=20:raise ValueError('Invalid observed channel')
        position=[number(request['position'][k]) for k in ('x','y')]
        if action=='measure':
            kind=response['measure_result']
            if kind not in ('direction','near','no_signal'):raise ValueError('Unknown observed measurement outcome')
        else:
            if response['clear_result'] not in ('success','no_target_in_range'):raise ValueError('Unknown clear outcome')
            kind='clear_success' if response['clear_result']=='success' else 'clear_fail'
        bearing=number(response['svd_deg']) if kind=='direction' else None
        projected.append(dict(action=action,channel=channel,position=position,kind=kind,bearing_deg=bearing,
                              event_end_us=end_us,delta_us=delta_us))
    return projected,previous_us

def active_history(projected,*,channel,position,theta_deg,snapshot_us):
    theta=math.radians(number(theta_deg));cs,sn=math.cos(theta),math.sin(theta)
    def xy(q):
        dx,dy=q[0]-position[0],q[1]-position[1]
        return [(cs*dx+sn*dy)/1800,(-sn*dx+cs*dy)/1800]
    kinds=('direction','near','no_signal','clear_fail','clear_success')
    values=[];previous_position=None;first_positive=None
    for event in projected:
        if event['channel']!=channel:continue
        end_us=event['event_end_us'];age_us=snapshot_us-end_us
        if age_us<0:raise ValueError('Future event in public snapshot')
        kind=event['kind'];has_bearing=kind=='direction';location=event['position']
        if has_bearing and first_positive is None:
            first_positive=len(values)
            if abs(((event['bearing_deg']-theta_deg+180)%360)-180)>1e-7:
                raise ValueError('Controller first bearing differs from full public history')
        relative=math.radians(event['bearing_deg']-theta_deg) if has_bearing else 0.
        values.append([*[float(kind==k) for k in kinds],*xy(location),
            math.sin(relative) if has_bearing else 0.,math.cos(relative) if has_bearing else 0.,float(has_bearing),
            age_us/1e10,float(previous_position==location),event['delta_us']/2_300_000_000,
            float(has_bearing and first_positive==len(values))])
        previous_position=location
    if first_positive is None:raise ValueError('Missing active-channel positive bearing')
    indexes=set(range(max(0,len(values)-127),len(values)));indexes.add(first_positive)
    kept=[values[i] for i in sorted(indexes)]
    return kept,len(values)-len(kept)

def validate_features(features):
    if type(features) is not dict or set(features)!=TENSOR_KEYS:raise ValueError('Unknown or missing feature tensor fields')
    dimensions={'global_features':(20,), 'channels':(20,12),'polygon':(32,2)}
    for key,dims in dimensions.items():
        value=features[key]
        if type(value) is not list or len(value)!=dims[0]:raise ValueError('Feature dimension mismatch: '+key)
        if len(dims)>1 and any(type(row) is not list or len(row)!=dims[1] for row in value):
            raise ValueError('Feature row dimension mismatch: '+key)
    events=features['active_events'];mask=features['active_mask'];actions=features['actions']
    if not (type(events) is list and 1<=len(events)<=128 and all(type(row) is list and len(row)==14 for row in events)):
        raise ValueError('Invalid active event tensor')
    if type(mask) is not list or len(mask)!=len(events) or not any(mask) or any(type(v) is not bool for v in mask):
        raise ValueError('Invalid active event mask')
    if not(type(actions) is list and 1<=len(actions)<=9 and all(type(row) is list and len(row)==14 for row in actions)):
        raise ValueError('Invalid action tensor')
    for key in TENSOR_KEYS-{'active_mask'}:
        rows=[features[key]] if key=='global_features' else features[key]
        for row in rows:
            for value in row:number(value)
    return features

def validate_snapshot(snapshot):
    if type(snapshot) is not dict or set(snapshot)!={'schema','candidate_ids','teacher_id','features','diagnostics'}:
        raise ValueError('Unknown actor snapshot fields')
    if snapshot['schema']!='bc-rpi-r1-public-features-v1':raise ValueError('Unknown actor snapshot version')
    ids=snapshot['candidate_ids'];teacher=snapshot['teacher_id']
    if type(ids) is not list or not 1<=len(ids)<=9 or len(set(ids))!=len(ids) or ids!=sorted(ids):
        raise ValueError('Invalid canonical candidate IDs')
    if any(type(v) is not str or len(v)!=64 or any(c not in '0123456789abcdef' for c in v) for v in ids):
        raise ValueError('Candidate IDs are not canonical hashes')
    if teacher not in ids:raise ValueError('Teacher absent from retained IDs')
    validate_features(snapshot['features'])
    if len(ids)!=len(snapshot['features']['actions']):raise ValueError('Action/ID alignment mismatch')
    if type(snapshot['diagnostics']) is not dict or set(snapshot['diagnostics'])!={'events_dropped','public_event_count'}:
        raise ValueError('Unknown public feature diagnostics')
    if any(type(v) is not int or v<0 for v in snapshot['diagnostics'].values()):raise ValueError('Invalid public diagnostic count')
    return snapshot

def build_snapshot(prepared,events):
    """Accept PreparedChoice JSON plus public API events, never a ForkHandle."""
    if hasattr(prepared,'to_json'):prepared=prepared.to_json()
    if type(prepared) is not dict or not {'choices','public_controller','meta'}<=set(prepared):
        raise ValueError('Prepared public choice required')
    choices=prepared['choices'];controller=decode(prepared['public_controller'])
    if any(str(r).startswith('generator_error:') for r in choices['rejections']):raise ValueError('Candidate generation failed')
    if prepared['meta']['teacher_task']['kind']!='source':raise ValueError('Only source entries have actor features')
    channel=prepared['meta']['teacher_task']['key'];position=controller['position']
    theta=controller['observations'][channel][0][1]
    projected,last_us=event_projection(events);snapshot_us=round(number(controller['virtual_time'])*1e6)
    if snapshot_us!=last_us:raise ValueError('Controller/public prefix virtual time differs')
    values,dropped=active_history(projected,channel=channel,position=position,theta_deg=theta,snapshot_us=snapshot_us)
    features={key:deepcopy(choices['features'][key]) for key in TENSOR_KEYS}
    features['active_events']=values;features['active_mask']=[True]*len(values)
    result=dict(schema='bc-rpi-r1-public-features-v1',candidate_ids=list(choices['candidate_ids']),
        teacher_id=choices['teacher_id'],features=features,
        diagnostics=dict(events_dropped=dropped,public_event_count=len(events)))
    return validate_snapshot(result)
