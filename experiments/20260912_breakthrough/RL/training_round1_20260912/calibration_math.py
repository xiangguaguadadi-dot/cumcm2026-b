"""Pure empirical world-level calibration; not a coverage guarantee."""
import math

def world_residual(states):
    if not states:raise ValueError('No sampled calibration state; do not invent an empty max=0')
    if len(states)>2:raise ValueError('Too many registered calibration states')
    values=[]
    for state in states:
        if state['candidate_id']==state['teacher_id']:
            if state['predicted_gain']!=0. or state['realized_gain']!=0.:
                raise ValueError('A0 selected calibration residual must be exactly zero')
        a,b=state['predicted_gain'],state['realized_gain']
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (a,b)):
            raise ValueError('Nonfinite calibration value')
        residual=a-b
        if not math.isfinite(residual):raise ValueError('Nonfinite optimistic residual after subtraction')
        values.append(residual)
    return max(values)

def margin_from_worlds(rows,registered_world_ids):
    if len(registered_world_ids)!=24 or len(set(registered_world_ids))!=24:
        raise ValueError('Calibration requires exactly 24 registered unique worlds')
    if len(rows)!=24 or len({r['world_id'] for r in rows})!=24 or {r['world_id'] for r in rows}!=set(registered_world_ids):
        raise ValueError('Incomplete/misbound calibration world set')
    values=[]
    for row in rows:
        if row['status']!='complete':raise ValueError('Unfinished calibration world')
        value=world_residual(row['states'])
        if value!=row['world_max_optimistic_residual']:raise ValueError('World maximum residual differs')
        values.append(value)
    ordered=sorted(values);rank=math.ceil(0.9*len(values));q=max(0.,ordered[rank-1])
    return dict(margin=q,nearest_rank=rank,world_count=24,raw_rank_value=ordered[rank-1],
        sorted_world_residuals=ordered,strict_extra_gain=0.0005,
        scope='Empirical margin only on frozen C7 sampled-state distribution, not a conformal/full-trajectory or second-intervention coverage guarantee')
