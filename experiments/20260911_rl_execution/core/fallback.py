"""Independent finite backup; never re-enters or reads hidden source data."""
from __future__ import annotations
from .geometry import discovery_stations, optical_grid, fallback_paper_bounds
from .interface import InterfaceFailure

def run_fallback(api):
    if not api.started:raise InterfaceFailure('Fallback requires an entered task')
    if api.phase!='fallback':raise InterfaceFailure('Fallback must be irreversible')
    start_time=api.virtual_time;start_event=len(api.events)
    silent={c:set() for c in range(1,21)}
    stations=discovery_stations()
    for station_index,p in enumerate(stations):
        for ch in range(1,21):
            if ch in api.cleared:continue
            if len(api.cleared)>=16:break
            r=api.measure(*p,ch)
            kind=r['measure_result']
            if kind=='no_signal':
                silent[ch].add(station_index)
            elif kind=='near':
                if api.clear(*p,ch)['clear_result']!='success':
                    raise InterfaceFailure('Fallback near-clear certificate contradicted')
            else:
                for q in optical_grid(p,r['svd_deg']):
                    if api.clear(*q,ch)['clear_result']=='success':break
                else:
                    raise InterfaceFailure('Fallback optical coverage certificate contradicted')
        if len(api.cleared)>=16:break
    unresolved=[c for c in range(1,21) if c not in api.cleared]
    if len(api.cleared)>=16:
        certificate={'type':'observed_16_distinct_clear_successes'}
    elif all(len(silent[c])==49 for c in unresolved):
        if any(obs[0] in unresolved for obs in api.positive_observations):
            raise InterfaceFailure('Positive history contradicts fallback certified absence')
        if not 10<=len(api.cleared)<=16:
            raise InterfaceFailure('Public source-count lower bound contradicts fallback completion')
        certificate={'type':'independent_49_station_coverage',
                     'absent_channels':unresolved,'scanned_station_count':49}
    else:
        raise InterfaceFailure('Fallback ended without coverage certificate')
    api.exit_certificate=certificate
    response=api.exit()
    elapsed=api.virtual_time-start_time
    requests=len(api.events)-start_event
    if requests>5845 or elapsed>53000+0.01:
        raise InterfaceFailure('Fallback exceeded paper budget')
    return {'certificate':certificate,'exit_response':response,
            'tail_time_s':elapsed,'business_requests':requests,
            'bounds':fallback_paper_bounds()}
