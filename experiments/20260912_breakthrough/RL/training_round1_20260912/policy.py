"""Observable READY selector with frozen model/margin and exact teacher fallback."""
from __future__ import annotations
import math
import time
from .features import build_snapshot
from .selection import gated_choice

class Policy:
    def __init__(self,worker,margin,*,force_teacher=False):
        if type(margin) not in (int,float) or not math.isfinite(margin) or margin<0:raise ValueError('Invalid fixed calibration margin')
        self.worker=worker;self.margin=float(margin);self.force_teacher=bool(force_teacher)
        self.decisions=[];self.disabled=False

    def reset_episode(self):self.decisions=[]

    def select(self,engine,prepared):
        teacher=prepared.choices['teacher_id'];task=prepared.meta['teacher_task']
        start=time.monotonic();common_prepare_wall=prepared.prepare_wall_s
        row=dict(choice_id=prepared.choice_id,teacher_id=teacher,selected_id=teacher,
                 checkpoint_sha256=self.worker.checkpoint_sha,task_kind=task['kind'],mode=engine.s.mode,
                 margin=self.margin,force_teacher_probe=self.force_teacher,batch_size=1,model_scored=False)
        try:
            if task['kind']!='source' or engine.s.mode!=4:
                row['rejection']='not_q4_source';return teacher
            b=engine.state['interventions_remaining'];channel=task['key'];row['slots_before']=b
            if type(b) is not int or not 0<=b<=2:
                row['rejection']='invalid_slots';return teacher
            if b==0 or channel in engine.state['forced_teacher_channels']:
                row['rejection']='slots_or_forced_teacher';return teacher
            if self.disabled or self.worker.disabled:
                row['rejection']='neural_worker_disabled';return teacher
            engine.expand(prepared)
            if any(str(v).startswith('generator_error:') and 'MemoryError' in str(v)
                   for v in prepared.choices['rejections']):
                # The frozen legacy candidate IPC renders exceptions as text.
                # Preserve affirmative memory-failure evidence as a stop, not
                # a successful teacher-only policy run.
                raise MemoryError('Frozen candidate worker reported MemoryError')
            if any(str(v).startswith('generator_error:') for v in prepared.choices['rejections']):
                raise ValueError('Public candidate generator rejected snapshot')
            if not prepared.choices['eligible'] or len(prepared.choices['candidate_ids'])==1:
                row.update(selected_id=teacher,rejection='not_eligible_or_teacher_only');return teacher
            snapshot=build_snapshot(prepared,engine.api.events)
            row['candidate_and_feature_wall_s']=time.monotonic()-start
            scored=self.worker.score(snapshot)
            choice=gated_choice(snapshot['candidate_ids'],teacher,scored['scores'],self.margin)
            selected=teacher if self.force_teacher else choice['selected_id']
            row.update(selected_id=selected,predicted_candidate_id=choice['candidate_id'],predicted_gain=choice['predicted_gain'],
                model_scored=True,
                strict_threshold=choice['strict_threshold'],candidate_ids=snapshot['candidate_ids'],scores=scored['scores'],
                gains=choice['gains'],inference_roundtrip_wall_s=scored['roundtrip_wall_s'],
                model_forward_wall_s=scored['forward_wall_s'],model_forward_cpu_s=scored['forward_cpu_s'],
                tensor_build_wall_s=scored['tensor_build_wall_s'],tensor_build_cpu_s=scored['tensor_build_cpu_s'],
                events_dropped=snapshot['diagnostics']['events_dropped'],rejection=None)
            return selected
        except MemoryError as exc:
            row.update(selected_id=teacher,rejection='MemoryError: '+str(exc));raise
        except Exception as exc:
            if self.worker.disabled:self.disabled=True
            row.update(selected_id=teacher,rejection=type(exc).__name__+': '+str(exc))
            return teacher
        finally:
            row['selector_wall_s']=time.monotonic()-start
            row['complete_prepare_feature_ipc_forward_selection_wall_s']=common_prepare_wall+row['selector_wall_s']
            self.decisions.append(row)
