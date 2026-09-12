"""Pure retained-ID selection and explicit float32 score-difference semantics."""
import math
import struct

def float32(value):
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Nonfinite model score')
    try:result=struct.unpack('!f',struct.pack('!f',float(value)))[0]
    except (OverflowError,struct.error) as exc:raise ValueError('Score outside float32 range') from exc
    if not math.isfinite(result):raise ValueError('Nonfinite float32 score')
    return result

def predicted_choice(candidate_ids,teacher_id,scores):
    if type(candidate_ids) is not list or not 1<=len(candidate_ids)<=9 or candidate_ids!=sorted(candidate_ids):
        raise ValueError('Invalid canonical retained IDs')
    if len(set(candidate_ids))!=len(candidate_ids) or teacher_id not in candidate_ids:raise ValueError('Bad teacher/ID set')
    if any(type(v) is not str or len(v)!=64 or any(c not in '0123456789abcdef' for c in v) for v in candidate_ids):
        raise ValueError('Non-hash candidate ID')
    if type(scores) is not list or len(scores)!=len(candidate_ids):raise ValueError('Score/ID length mismatch')
    values=[float32(s) for s in scores]
    if any(s!=v for s,v in zip(scores,values)):raise ValueError('Actor scores must be exact float32 values')
    ref=candidate_ids.index(teacher_id);gains=[float32(s-values[ref]) for s in values]
    if gains[ref]!=0.:raise AssertionError('Teacher relative gain is nonzero')
    best=min(range(len(gains)),key=lambda i:(-gains[i],candidate_ids[i]))
    return dict(candidate_id=candidate_ids[best],candidate_index=best,teacher_index=ref,
                predicted_gain=gains[best],gains=gains)

def gated_choice(candidate_ids,teacher_id,scores,margin):
    if type(margin) not in (int,float) or not math.isfinite(margin) or margin<0:raise ValueError('Invalid fixed calibration margin')
    choice=predicted_choice(candidate_ids,teacher_id,scores)
    intervene=choice['candidate_id']!=teacher_id and choice['predicted_gain']>margin+0.0005
    return dict(choice,selected_id=choice['candidate_id'] if intervene else teacher_id,
                intervened=intervene,margin=float(margin),strict_threshold=float(margin)+0.0005)
