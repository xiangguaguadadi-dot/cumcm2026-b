"""One fixed three-seed supervised fit, from public fit/fit_val exports only."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random
import time
from .torch_runtime import configure,identity
torch=configure()
from .model import CounterfactualModel,EXPECTED_PARAMETER_COUNT
from .features import validate_snapshot,TENSOR_KEYS
from .common import ROOT,SEEDS,load,save_new,sha,atomic_json
from .budget import Budget,BudgetStop

def tensors(features):
    return {key:torch.tensor(features[key],dtype=torch.bool if key=='active_mask' else torch.float32)
            for key in TENSOR_KEYS}

def state_loss(scores,targets,teacher_index):
    if scores.ndim!=1 or targets.shape!=scores.shape or not 0<=teacher_index<len(scores):
        raise ValueError('Paired-score target shape/reference differs')
    if not torch.isfinite(targets).all() or not torch.isfinite(scores).all():raise ValueError('Nonfinite complete labels/scores')
    if targets[teacher_index].item()!=0.:raise ValueError('Reference target must be exactly zero')
    if len(scores)==1:return scores.sum()*0.
    selected=torch.arange(len(scores))!=teacher_index
    residual=(scores-scores[teacher_index]-targets)/0.002
    z=residual[selected];absolute=z.abs()
    return torch.where(absolute<=1,0.5*z.square(),absolute-0.5).mean()

def world_loss(model,world):
    states=world['states']
    if not states:return next(model.parameters()).sum()*0.
    values=[]
    for state in states:
        if len(state['targets_normalized'])==1:
            values.append(next(model.parameters()).sum()*0.);continue
        scores=model(state['_tensors'])
        values.append(state_loss(scores,state['_targets'],state['teacher_index']))
    return torch.stack(values).mean()

def batch_loss(model,worlds):
    if not worlds:raise ValueError('Empty world batch')
    return torch.stack([world_loss(model,w) for w in worlds]).mean()

def validation_predictions(model,worlds):
    """Retain candidate-ID aligned forward outputs for independent loss audit."""
    records=[];world_values=[]
    with torch.no_grad():
        for world in worlds:
            state_records=[];state_values=[]
            for state in world['states']:
                scores=model(state['_tensors']);ref=state['teacher_index'];gains=scores-scores[ref]
                value=state_loss(scores,state['_targets'],ref);state_values.append(value)
                state_records.append(dict(choice_id=state['choice_id'],candidate_ids=state['snapshot']['candidate_ids'],
                    teacher_id=state['snapshot']['teacher_id'],teacher_index=ref,raw_scores_float32=scores.tolist(),
                    paired_gains_float32=gains.tolist(),targets_normalized_original=state['targets_normalized'],
                    targets_float32=state['_targets'].tolist(),state_world_weighted_component=float(value)))
            value=torch.stack(state_values).mean() if state_values else next(model.parameters()).sum()*0.
            world_values.append(value)
            records.append(dict(world_id=world['world_id'],world_sha256=world['world_sha256'],role=world['role'],
                state_count=len(state_values),states=state_records,world_equal_state_loss=float(value)))
        average=float(torch.stack(world_values).mean())
    return dict(schema='bc-rpi-r1-fit-val-forward-audit-v1',worlds=records,world_equal_mean_loss=average,
        tensor_dtype='float32',loss_scale=0.002,no_gradient=True,selection_role='fit_val_only')

def verify_dataset(directory,manifest,manifest_sha):
    if sha(directory/'manifest.json')!=manifest_sha:raise RuntimeError('Loaded public manifest changed during fit')
    for entry in manifest['worlds']:
        path=(directory/entry['path']).resolve()
        if path.parent!=directory or sha(path)!=entry['sha256']:
            raise RuntimeError('Loaded public world export changed during fit')

def load_public_dataset(directory):
    directory=Path(directory).resolve();manifest_path=directory/'manifest.json';manifest=load(manifest_path)
    manifest_keys={'schema','worlds','counts','state_bundles','nonreference_labels','teacher_only_states','zero_state_worlds',
        'label_scale','continuation_policy_sha256','shared_for_three_independent_initializations','trusted_exporter_sha256',
        'feature_implementation_sha256','source_collection_summary_sha256','source_world_results_sha256','read_boundary'}
    if set(manifest)!=manifest_keys or manifest.get('schema')!='bc-rpi-round1-public-fit-manifest-v1' or manifest['counts']!={'fit':24,'fit_val':12}:
        raise ValueError('Not the fixed public fit/fit_val dataset')
    if manifest['label_scale']!=0.002 or manifest['feature_implementation_sha256']!=sha(ROOT/'features.py'):
        raise ValueError('Fit feature identity/normalization changed')
    roles={'fit':[],'fit_val':[]};opened=[str(manifest_path)];ids=set();hashes=set()
    for entry in manifest['worlds']:
        if set(entry)!={'role','world_id','world_sha256','path','sha256','states'}:raise ValueError('Unknown public manifest entry fields')
        if entry['role'] not in roles:raise ValueError('Forbidden role in fitter input')
        path=(directory/entry['path']).resolve()
        if path.parent!=directory:raise ValueError('Fitter input escaped public export directory')
        if sha(path)!=entry['sha256']:raise ValueError('Public dataset content changed')
        world=load(path);opened.append(str(path))
        if set(world)!={'schema','world_id','world_sha256','role','states','state_count','complete','no_world_truth','empty_state_and_world_weight'}:
            raise ValueError('Unexpected public training world fields')
        if not world['complete'] or not world['no_world_truth'] or world['role']!=entry['role']:
            raise ValueError('World role/completion mismatch')
        if world['world_id']!=entry['world_id'] or world['world_sha256']!=entry['world_sha256']:
            raise ValueError('World identity mismatch')
        if world['world_id'] in ids or world['world_sha256'] in hashes:raise ValueError('Duplicate fit/val world')
        ids.add(world['world_id']);hashes.add(world['world_sha256'])
        if len(world['states'])!=world['state_count']:raise ValueError('World state denominator differs')
        for state in world['states']:
            if set(state)!={'snapshot','targets_normalized','teacher_index','origin_run_ids','reference_origin_run_id',
                'choice_id','source_index','state_index','complete_bundle','continuation_policy_sha256'}:
                raise ValueError('Unexpected state data outside public fit schema')
            validate_snapshot(state['snapshot'])
            if not state['complete_bundle'] or state['continuation_policy_sha256']!=manifest['continuation_policy_sha256']:
                raise ValueError('Incomplete or stale-tail labels')
            ids_a=state['snapshot']['candidate_ids'];ref=state['teacher_index']
            if not 0<=ref<len(ids_a) or ids_a[ref]!=state['snapshot']['teacher_id']:
                raise ValueError('Teacher/reference index not aligned')
            if len(state['targets_normalized'])!=len(ids_a) or len(state['origin_run_ids'])!=len(ids_a):
                raise ValueError('Label/retained action count differs')
            state['_tensors']=tensors(state['snapshot']['features'])
            state['_targets']=torch.tensor(state['targets_normalized'],dtype=torch.float32)
            if not torch.isfinite(state['_targets']).all() or state['_targets'][ref]!=0:
                raise ValueError('Invalid normalized target')
        roles[world['role']].append(world)
    if {k:len(v) for k,v in roles.items()}!={'fit':24,'fit_val':12}:raise ValueError('Role counts differ')
    return roles,manifest,opened

def state_digest(model):
    hasher=hashlib.sha256()
    for name,value in sorted(model.state_dict().items()):
        hasher.update(name.encode());hasher.update(value.detach().cpu().contiguous().numpy().tobytes())
    return hasher.hexdigest()

def save_checkpoint(path,payload):
    if path.exists():raise FileExistsError('Checkpoint exists; do not overwrite')
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_name(path.name+'.pending')
    torch.save(payload,temporary);temporary.replace(path)

def append_fit(path,row):
    with path.open('a') as stream:
        stream.write(json.dumps(dict(row,recorded_utc=datetime.now(timezone.utc).isoformat()),separators=(',',':'),allow_nan=False)+'\n')

def train_one(seed,roles,dataset_sha,out,journal,budget):
    budget.check_resources()
    torch.manual_seed(seed);shuffle=random.Random(seed+17)
    model=CounterfactualModel();optimizer=torch.optim.Adam(model.parameters(),lr=3e-4,weight_decay=1e-5)
    if sum(p.numel() for p in model.parameters() if p.requires_grad)!=EXPECTED_PARAMETER_COUNT:raise AssertionError('Parameter count differs')
    initial_sha=state_digest(model);started=time.monotonic();started_cpu=time.process_time()
    run_id='r1_seed_'+str(seed)
    append_fit(journal,dict(event='fit_start',run_id=run_id,seed=seed,initial_parameter_sha256=initial_sha,
        dataset_manifest_sha256=dataset_sha,fit_worlds=24,fit_val_worlds=12,expected_updates=60,epochs=20))
    budget.data['network_training_runs']+=1;budget.data.setdefault('fit_updates',0);budget.set_status('fitting_'+run_id)
    history=[];checkpoints=[];update=0
    save_checkpoint(out/f'initial_{seed}.pt',dict(schema='bc-rpi-r1-initial-weights-v1',seed=seed,
        model_state_dict=model.state_dict(),parameter_sha256=initial_sha,dataset_manifest_sha256=dataset_sha))
    for epoch in range(1,21):
        order=list(range(24));shuffle.shuffle(order);model.train();batch_values=[]
        for offset in range(0,24,8):
            selected=order[offset:offset+8];optimizer.zero_grad(set_to_none=True)
            loss=batch_loss(model,[roles['fit'][i] for i in selected])
            if not torch.isfinite(loss):raise RuntimeError('Nonfinite supervised fit loss')
            loss.backward();grad_norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
            if not torch.isfinite(grad_norm):raise RuntimeError('Nonfinite fit gradient')
            optimizer.step();update+=1;budget.data['fit_updates']+=1
            value=float(loss.detach());batch_values.append(value)
            append_fit(journal,dict(event='optimizer_update',run_id=run_id,seed=seed,epoch=epoch,update=update,
                fit_world_ids=[roles['fit'][i]['world_id'] for i in selected],
                loss=value,gradient_norm_before_clip=float(grad_norm),batch_worlds=8))
        row=dict(epoch=epoch,updates=update,train_mean_of_equal8world_batch_losses=sum(batch_values)/len(batch_values))
        if epoch in (5,10,20):
            model.eval()
            predictions=validation_predictions(model,roles['fit_val']);validation=predictions['world_equal_mean_loss']
            if not torch.isfinite(torch.tensor(validation)):raise RuntimeError('Nonfinite fit_val score')
            row['fit_val_world_equal_loss']=validation
            parameter_sha=state_digest(model);path=out/f'seed_{seed}_epoch_{epoch:02d}.pt'
            prediction_path=out/f'seed_{seed}_epoch_{epoch:02d}_fit_val_predictions.json'
            save_new(prediction_path,dict(predictions,seed=seed,epoch=epoch,parameter_sha256=parameter_sha,
                dataset_manifest_sha256=dataset_sha))
            save_checkpoint(path,dict(schema='bc-rpi-r1-neural-checkpoint-v1',seed=seed,epoch=epoch,updates=update,
                parameter_count=EXPECTED_PARAMETER_COUNT,model_state_dict=model.state_dict(),
                optimizer_state_dict=optimizer.state_dict(),torch_rng_state=torch.get_rng_state(),
                python_shuffle_rng_state=shuffle.getstate(),parameter_sha256=parameter_sha,
                initial_parameter_sha256=initial_sha,dataset_manifest_sha256=dataset_sha,
                model_source_sha256=sha(ROOT/'model.py'),feature_implementation_sha256=sha(ROOT/'features.py'),
                fit_val_world_equal_loss=validation,loss_scale=0.002,ranking_weight=0.,
                hyperparameters=dict(optimizer='Adam',lr=3e-4,weight_decay=1e-5,batch_worlds=8,grad_clip=1.)))
            checkpoints.append(dict(path=path.name,sha256=sha(path),epoch=epoch,updates=update,
                parameter_sha256=parameter_sha,fit_val_world_equal_loss=validation,
                model_source_sha256=sha(ROOT/'model.py'),feature_implementation_sha256=sha(ROOT/'features.py'),
                validation_predictions_path=prediction_path.name,validation_predictions_sha256=sha(prediction_path)))
            append_fit(journal,dict(event='checkpoint_saved',run_id=run_id,seed=seed,**checkpoints[-1]))
        history.append(row)
        atomic_json(out/f'seed_{seed}_history.json',dict(seed=seed,epochs=history))
    selected=min(checkpoints,key=lambda c:(c['fit_val_world_equal_loss'],c['epoch']))
    final_sha=state_digest(model)
    if final_sha==initial_sha:raise RuntimeError('No model parameter changed despite claimed fitting')
    row=dict(seed=seed,status='complete',updates=update,epochs=20,checkpoints=checkpoints,selected=selected,
        selection='Lowest world-equal regression loss on permanent fit_val; ties choose earlier preregistered epoch',
        initial_parameter_sha256=initial_sha,final_parameter_sha256=final_sha,
        fit_wall_s=time.monotonic()-started,fit_cpu_s=time.process_time()-started_cpu)
    save_new(out/f'seed_{seed}_result.json',row)
    append_fit(journal,dict(event='fit_finish',run_id=run_id,seed=seed,status='complete',updates=update,
                          selected_epoch=selected['epoch'],selected_checkpoint_sha256=selected['sha256'],
                          fit_wall_s=row['fit_wall_s'],fit_cpu_s=row['fit_cpu_s']))
    budget.data.setdefault('network_training_completed',0);budget.data['network_training_completed']+=1;budget.save()
    return row

def run(dataset,out,acceptance_path):
    dataset=(ROOT/dataset).resolve();out=(ROOT/out).resolve();acceptance=load(acceptance_path)
    dataset.relative_to(ROOT);out.relative_to(ROOT)
    if acceptance.get('fit_accepted') is not True:raise RuntimeError('Coordinator fit acceptance required')
    dataset_sha=sha(dataset/'manifest.json')
    if acceptance.get('dataset_manifest_sha256')!=dataset_sha:
        raise RuntimeError('Accepted fit dataset differs')
    source_path=(ROOT/acceptance['fit_source_freeze_path']).resolve();source_path.relative_to(ROOT)
    if acceptance.get('fit_source_freeze_sha256')!=sha(source_path):raise RuntimeError('Accepted fit source freeze differs')
    source_manifest=load(source_path)
    from .freeze import verify_sources
    from .stage_freeze import verify_stage_sources
    verify_stage_sources(source_manifest,'fit')
    if out.exists():raise FileExistsError('Use fresh fit output directory; no silent rerun')
    out.mkdir(parents=True)
    roles,manifest,opened=load_public_dataset(dataset);budget=Budget();journal=out/'fit_journal.jsonl'
    verify_dataset(dataset,manifest,dataset_sha)
    save_new(out/'read_log.json',dict(allowed_roles=['fit','fit_val'],opened_dataset_files=opened,
        dataset_manifest_sha256=dataset_sha,world_truth_loaded=False))
    save_new(out/'runtime.json',identity());results=[];status='fitting';reason=None
    try:
        for seed in SEEDS:
            verify_sources(source_manifest);verify_dataset(dataset,manifest,dataset_sha)
            results.append(train_one(seed,roles,dataset_sha,out,journal,budget))
            verify_sources(source_manifest);verify_dataset(dataset,manifest,dataset_sha)
            print({'seed':seed,'status':'complete','selected_epoch':results[-1]['selected']['epoch'],
                   'updates':results[-1]['updates']},flush=True)
        if len({r['initial_parameter_sha256'] for r in results})!=3:raise RuntimeError('Initializations were not independent')
        status='three_seed_fit_complete_not_calibrated'
    except BudgetStop as exc:status='fit_incomplete_resource';reason=str(exc)
    except BaseException as exc:
        status='fit_incomplete_engineering';reason=type(exc).__name__+': '+str(exc);raise
    finally:
        budget.set_status(status)
        save_new(out/'summary.json',dict(status=status,stop_reason=reason,registered_seeds=SEEDS,
            completed_seeds=[r['seed'] for r in results],results=results,
            actual_new_environment_calls=0,optimizer_updates=sum(r['updates'] for r in results),
            failed_or_partial_fit_updates_retained_in_journal=True,
            cumulative_actual_calls=budget.data['business_calls'],dataset_manifest_sha256=dataset_sha,
            fit_source_freeze_sha256=sha(source_path),model_source_sha256=sha(ROOT/'model.py'),
            feature_implementation_sha256=sha(ROOT/'features.py')))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',required=True);p.add_argument('--out',required=True)
    p.add_argument('--acceptance',required=True);a=p.parse_args();run(a.dataset,a.out,a.acceptance)
