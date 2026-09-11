"""C7 service methods with detached macro candidates and a shared selector.

Only online interface observations enter this module. True task source count
is deliberately absent; runners attach terminal labels after this returns.
"""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import math
from pathlib import Path
import time

from .schema import (SCHEMA_VERSION,GENERATOR_VERSION,canonical_json,stable_id,
                     freeze_copy,validate_snapshot,teacher_selector)
from .geometry import polygon_area
from .interface import GuardConfig,MeteredInterface,FallbackRequired,InterfaceFailure
from .fallback import run_fallback

C7_SHA256='cf37866829b9c6f376895075e819a732939e6fa8ad6d8d6297a151d7a213dcb3'
_C7=None

def load_c7():
    global _C7
    if _C7 is None:
        root=Path(__file__).resolve().parents[3]
        path=root/'experiments/20260911_stage4/combination/geometry_fusions/C7_both.py'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=C7_SHA256:
            raise RuntimeError('C7 pinned source hash changed')
        spec=importlib.util.spec_from_file_location('_rl_execution_pinned_c7',path)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        _C7=m
    return _C7

def _plain(v):
    if isinstance(v,dict):return {str(k):_plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [_plain(x) for x in v]
    if isinstance(v,set):return [_plain(x) for x in sorted(v)]
    if v is None or type(v) in (bool,int,str):return v
    if type(v) is float:
        if not math.isfinite(v):return {'nonfinite':str(v)}
        return v
    raise TypeError('Unsupported observable controller state: '+type(v).__name__)

def _copy_controller(s):
    clone=copy.copy(s)
    clone.__dict__={k:(v if k=='env' else copy.deepcopy(v)) for k,v in s.__dict__.items()}
    return clone

def _circle(s,poly):
    m=load_c7()
    return (m._Q3._sp_enclosing_circle(poly) if s.mode==3 else m._Q4._di_enclosing_circle(poly))

def _pending(s):
    return [c for c in range(1,21) if s.observations[c] and c not in s.cleared]

def _waive_discovery(s,todo):
    # Literal conditions from the respective pinned C7 run loops.
    if s.mode==3:
        if todo and s.all_sources_discovered():
            s.counters['stations_waived_after_all_discovered']=len(todo);todo.clear()
    elif (todo and s.config.get('stop_discovered',True)
            and s.config.get('upper_bound_stop',True) and s.config.get('joint_scheduling',False)):
        discovered={c for c in range(1,21) if c in s.cleared or s.observations[c]}
        ready=s.config.get('discovered_ready_radius',float('inf'))
        if len(discovered)>=16 and all(_circle(s,s.polygons[c])[1]<=ready
                                     for c in discovered if c not in s.cleared):
            s.counters['stations_removed_after_discovery']=s.counters.get('stations_removed_after_discovery',0)+len(todo)
            todo.clear()

def _teacher_task(s,todo):
    """Compute the exact original immediate task on a detached controller."""
    s.route_successor=None
    pending=_pending(s)
    if s.mode==3:
        ready=(s.mode==3 or (pending and all(_circle(s,s.polygons[c])[1]
                                <=s.config.get('clear_trial_radius',100) for c in pending)))
        spatial=ready and s.config.get('spatial_route',True)
    else:
        ready=bool(pending) and all(_circle(s,s.polygons[c])[1]
                                   <=s.config.get('spatial_ready_radius',100.) for c in pending)
        spatial=s.config.get('spatial_route',False) and (ready or not pending)
    if spatial:
        kind,key=s.spatial_next_task(todo)
        return kind,key,True
    if s.config.get('joint_scheduling',False):
        index=s.next_station(todo) if todo else None
        if pending:
            ch=min(pending,key=lambda c:math.dist(s.position,_circle(s,s.polygons[c])[0]))
            target=_circle(s,s.polygons[ch])[0]
            source_cost=math.dist(s.position,target)*s.config.get('source_priority',1.)
            station_cost=math.dist(s.position,s.points[index]) if index is not None else float('inf')
            if source_cost<=station_cost:return 'source',ch,True
        if index is None:raise RuntimeError('C7 chose missing discovery station')
        return 'station',index,True
    return 'station',s.next_station(todo),False

def _state(s,todo):
    # All fields are algorithm memory derived from earlier public responses.
    # Environment, callables and absolute deadlines never leave the engine.
    state={k:_plain(v) for k,v in s.__dict__.items()
           if k not in ('env','deadline','trace','e2_decisions')}
    state['todo']=sorted(todo);state['mode']=s.mode
    return state

def _progress(s,api):
    return (len(api.positive_observations),len(api.cleared),
            sum(len(x) for x in s.scanned.values()),
            sum(polygon_area(s.polygons[c]) if c in s.polygons else math.pi*1800**2
                for c in range(1,21) if c not in api.cleared))

def _has_progress(before,after):
    return after[0]>before[0] or after[1]>before[1] or after[2]>before[2] or after[3]<before[3]-1e-6

def _controller_patch(before,after):
    # Candidate generation in pinned C7 mutates only derived controller memory;
    # retain exact differences so selecting teacher commits the same effects.
    patch={}
    for k,v in after.__dict__.items():
        if k in ('env','deadline'):continue
        if k not in before.__dict__ or v!=before.__dict__[k]:patch[k]=copy.deepcopy(v)
    return patch

def _payload(s,kind,key,defer,successor,state_version,patch):
    target=(s.points[key] if kind=='station' else _circle(s,s.polygons[key])[0]
            if kind=='source' else s.position)
    progress=getattr(s,'_e2_progress',{})
    return {'kind':kind,'index':int(key) if key is not None else None,
        'channel':int(key) if kind=='source' else None,'target':list(target),
        'route_successor':list(successor) if successor is not None else None,
        'stage':'source_service' if kind=='source' else 'station_scan_deferred' if defer else 'station_scan_full',
        'defer':bool(defer),'state_version':state_version,
        'service_state':({name:_plain(getattr(s,name,{}).get(key))
                          for name in ('_e2_progress','_e2_failed_clear','failed_clear_points')}
                         if kind=='source' else None),
        'controller_patch':_plain(patch),'generator_version':GENERATOR_VERSION,
        'service_implementation_sha256':C7_SHA256,
        'stop_contract':{'primitive_guard':True,'return':'macro_completion_or_takeover',
                         'learning_box_m':4000,'max_learning_requests':10000}}

def build_snapshot(s,todo,api,decision_id,no_progress,previous_macro_s):
    """Generate complete candidates without mutating the live C7 controller."""
    before_state=_state(s,todo)
    state_version=hashlib.sha256(canonical_json(before_state).encode()).hexdigest()
    event_count=len(api.events)
    teacher_clone=_copy_controller(s)
    kind,key,defer=_teacher_task(teacher_clone,set(todo))
    if len(api.events)!=event_count:raise RuntimeError('Candidate enumeration performed an interface request')
    teacher_patch=_controller_patch(s,teacher_clone)
    teacher_payload=_payload(s,kind,key,defer,getattr(teacher_clone,'route_successor',None),state_version,teacher_patch)
    teacher_id=stable_id(teacher_payload)
    objects={teacher_id:(teacher_payload,teacher_patch)}
    tasks=[('station',i) for i in sorted(todo)]+[('source',c) for c in _pending(s)]
    positions={(t,k):(s.points[k] if t=='station' else _circle(s,s.polygons[k])[0]) for t,k in tasks}
    for task_kind,task_key in tasks:
        if (task_kind,task_key)==(kind,key):continue
        target=positions[(task_kind,task_key)]
        others=[(math.dist(target,p),t,k,p) for (t,k),p in positions.items() if (t,k)!=(task_kind,task_key)]
        successor=min(others)[-1] if others else None
        patch={'route_successor':successor}
        payload=_payload(s,task_kind,task_key,True,successor,state_version,patch)
        objects[stable_id(payload)]=(payload,patch)
    fb=_payload(s,'fallback',None,False,None,state_version,{})
    fb['stage']='independent_fallback';fb['stop_contract']={'return':'true_terminal','max_business_requests':5845}
    objects[stable_id(fb)]=(fb,{})
    ordered=sorted(objects)
    # At most 22 stations+16 pending sources+fallback under the shared source bound.
    if len(ordered)>64:raise RuntimeError('Candidate cap exceeded without a registered truncation rule')
    payloads=[objects[k][0] for k in ordered]
    masks=[p['kind']=='fallback' or all(math.isfinite(v) and abs(v)<=api.guard.box_m for v in p['target']) for p in payloads]
    channels=[];summaries={}
    for ch in range(1,21):
        obs=s.observations[ch];poly=s.polygons.get(ch)
        center,radius=_circle(s,poly) if poly else ((0.,0.),1800.)
        area=polygon_area(poly) if poly else math.pi*1800**2
        last=obs[-1] if obs else ((0.,0.),0.)
        summaries[ch]=(center,radius,area)
        channels.append([ch/20.,float(ch in api.cleared),float(bool(obs)),len(obs)/64.,
            center[0]/1800.,center[1]/1800.,radius/3600.,area/(math.pi*1800**2),
            len(s.scanned[ch])/max(1,len(s.points)),last[0][0]/4000.,last[0][1]/4000.,last[1]/360.])
    known=api.cleared|{c for c in range(1,21) if s.observations[c]}
    global_features=[float(s.mode==3),float(s.mode==4),api.position[0]/4000.,api.position[1]/4000.,
        api.channel/20.,api.virtual_time/360000.,api.elapsed_real_s/1200.,len(api.cleared)/20.,len(known)/20.,
        (20-len(known))/20.,len(todo)/49.,api.learning_requests/10000.,no_progress/32.,
        decision_id/10000.,api.remaining_real_s/1200.,previous_macro_s/10000.]
    features=[]
    for p in payloads:
        source=p['kind']=='source';station=p['kind']=='station';fallback=p['kind']=='fallback'
        ch=p['channel'];target=p['target'];succ=p['route_successor']
        radius=summaries[ch][1] if source else 0.
        distance=math.dist(api.position,target)
        cost=distance/5+(5+int(ch!=api.channel) if source else 6*(20-len(known)) if station else 53000.)
        features.append([float(source),float(station),float(fallback),(ch or 0)/20.,
            (p['index'] if station else 0)/49.,target[0]/4000.,target[1]/4000.,
            distance/(8000*math.sqrt(2)),cost/10000.,radius/3600.,
            len(s.observations[ch])/64. if source else 0.,(20-len(known))/20.,
            succ[0]/4000. if succ else 0.,succ[1]/4000. if succ else 0.,
            float(succ is not None),float(source and radius<=20.)])
    snapshot={'schema_version':SCHEMA_VERSION,'generator_version':GENERATOR_VERSION,
        'decision_id':decision_id,'state_version':state_version,'observable_state':before_state,
        'global_features':global_features,'channel_features':channels,'candidate_features':features,
        'valid_mask':masks,'candidate_ids':ordered,'teacher_index':ordered.index(teacher_id),'candidates':payloads}
    validate_snapshot(snapshot)
    if _state(s,todo)!=before_state:raise RuntimeError('Candidate generation mutated live state')
    return freeze_copy(snapshot),{k:objects[k][1] for k in ordered}

def _normalize_choice(choice,snapshot):
    if isinstance(choice,dict):
        index=choice.get('index');metadata=choice.get('metadata',{})
    else:index=choice;metadata={}
    if type(index) is not int or not 0<=index<len(snapshot['candidates']):
        raise InterfaceFailure('Selector returned invalid candidate index')
    if not snapshot['valid_mask'][index]:raise InterfaceFailure('Selector chose masked candidate')
    return index,freeze_copy(metadata)

def _c7_certificate(s,api):
    if len(api.cleared)==16:return {'type':'observed_16_distinct_clear_successes'}
    if not 10<=len(api.cleared)<=16:return None
    unresolved=[c for c in range(1,21) if c not in api.cleared]
    if (not any(obs[0] in unresolved for obs in api.positive_observations) and
        all(not s.observations[c] and set(range(len(s.points)))<=s.scanned[c] for c in unresolved)):
        return {'type':'c7_geometric_coverage','absent_channels':unresolved,'station_count':len(s.points)}
    return None

def run_episode(env,mode=3,selector=None,guard=None,clock=time.monotonic,c7_config=None):
    """Run a full entered task; returns observable records, never hidden N.

    Cost contract: prefix_time_s + sum(decision.delta_time_s) + tail_time_s
    equals total_time_s, including failed or partially executed last macros.
    """
    if mode not in (3,4):raise ValueError('mode must be 3 or 4')
    selector=selector or teacher_selector
    api=MeteredInterface(env,guard=guard,clock=clock)
    s=load_c7().Solver(api,mode=mode,**(c7_config or {}))
    s.deadline=None  # every primitive uses the common API guard instead
    todo=set(range(len(s.points)));visited=[];decisions=[]
    no_progress=0;previous_macro=0.;prefix=0.;tail=0.;fallback_details=None
    exception=None;controller_recoveries=[];active=None;takeover_start=None
    try:
        s._accept(api.enter())
        prefix=api.virtual_time
        while todo or _pending(s):
            api.check_learning()
            _waive_discovery(s,todo)
            if not todo and not _pending(s):break
            if no_progress>=api.guard.no_progress_limit:
                api.request_takeover('no_progress_decision_cap')
            s.route_successor=None
            prepare_start=clock()
            snapshot,patches=build_snapshot(s,todo,api,len(decisions),no_progress,previous_macro)
            built_at=clock()
            index,metadata=_normalize_choice(selector(freeze_copy(snapshot)),snapshot)
            selected_at=clock()
            payload=snapshot['candidates'][index]
            active={'snapshot':snapshot,'index':index,'candidate_id':snapshot['candidate_ids'][index],
                'metadata':metadata,'start_time_s':api.virtual_time,'event_start':len(api.events),
                'snapshot_build_s':max(0.,built_at-prepare_start),
                'selector_s':max(0.,selected_at-built_at),
                'prepare_to_macro_s':max(0.,selected_at-prepare_start)}
            before_progress=_progress(s,api)
            if payload['kind']=='fallback':api.request_takeover('selector_chose_fallback')
            for k,v in patches[active['candidate_id']].items():setattr(s,k,copy.deepcopy(v))
            active['prepare_to_macro_s']=max(0.,clock()-prepare_start)
            if payload['kind']=='source':s.localize(payload['index'])
            else:
                s.scan_station(payload['index'],defer=payload['defer'])
                visited.append(payload['index']);todo.remove(payload['index'])
            active['delta_time_s']=api.virtual_time-active['start_time_s']
            active['event_range']=[active.pop('event_start'),len(api.events)]
            active['macro_completed']=True;decisions.append(active);active=None
            previous_macro=decisions[-1]['delta_time_s']
            no_progress=0 if _has_progress(before_progress,_progress(s,api)) else no_progress+1
            if s.config.get('upper_bound_stop',True) and len(api.cleared)>=16:break
        certificate=_c7_certificate(s,api)
        if certificate is None:api.request_takeover('c7_completion_certificate_missing')
        api.exit_certificate=certificate;api.exit()
    except FallbackRequired as e:
        takeover_start=api.virtual_time
        if active is not None:
            active['delta_time_s']=api.virtual_time-active['start_time_s']
            active['event_range']=[active.pop('event_start'),len(api.events)]
            active['macro_completed']=False;decisions.append(active);active=None
        api.start_fallback(str(e))
        try:fallback_details=run_fallback(api)
        except Exception as fb_error:exception=type(fb_error).__name__+': '+str(fb_error)
        tail=api.virtual_time-takeover_start
    except InterfaceFailure as e:
        exception=type(e).__name__+': '+str(e)
    except (RuntimeError,TimeoutError) as e:
        # A C7 geometric/controller contradiction can be recovered using only
        # the independent physical ledger; it is retained as a warning.
        controller_recoveries.append(type(e).__name__+': '+str(e))
        takeover_start=api.virtual_time
        if active is not None:
            active['delta_time_s']=api.virtual_time-active['start_time_s']
            active['event_range']=[active.pop('event_start'),len(api.events)]
            active['macro_completed']=False;decisions.append(active);active=None
        api.start_fallback('c7_controller_recovery')
        try:fallback_details=run_fallback(api)
        except Exception as fb_error:exception=type(fb_error).__name__+': '+str(fb_error)
        tail=api.virtual_time-takeover_start
    except Exception as e:
        exception=type(e).__name__+': '+str(e)
    if active is not None:
        active['delta_time_s']=api.virtual_time-active['start_time_s']
        active['event_range']=[active.pop('event_start'),len(api.events)]
        active['macro_completed']=False;decisions.append(active)
    accounted=prefix+sum(d['delta_time_s'] for d in decisions)+tail
    # Requests outside learning decisions can only be the prefix or fallback.
    # Preserve failure accounting rather than silently discarding a remainder.
    remainder=api.virtual_time-accounted
    if abs(remainder)>1e-6:
        if not decisions and takeover_start is None:prefix+=remainder
        else:exception=(exception+'; ' if exception else '')+'Macro cost partition mismatch'
    observed_complete=api.exited and api.exit_certificate is not None and exception is None
    return {'schema_version':'rl-core-episode-v1','mode':mode,'c7_sha256':C7_SHA256,
        'terminal':'success' if observed_complete else 'failure','success':observed_complete,
        'observed_completion_certified':observed_complete,'true_completeness_checked':False,
        'normal_exit':api.exited,'completion_certificate':api.exit_certificate,
        'observed_cleared_channels':sorted(api.cleared),'cleared_count':len(api.cleared),
        'total_time_s':api.virtual_time,'virtual_time_s':api.virtual_time,
        'prefix_time_s':prefix,'tail_time_s':tail,'decisions':decisions,'events':api.events,
        'fallback_reason':api.takeover_reason,'fallback_details':fallback_details,
        'learning_primitive_count':api.learning_requests,'business_primitive_count':len(api.events),
        'visited_points':visited,'error':exception,'controller_recoveries':controller_recoveries,
        'runtime_s':api.elapsed_real_s,'accounting_max_error_s':api.accounting_max_error_s,
        'cost_partition_error_s':abs(prefix+sum(d['delta_time_s'] for d in decisions)+tail-api.virtual_time),
        'guard':dict(api.guard.__dict__),'real_time_guarantee':'conditional_only'}
