#!/usr/bin/env python3
"""Check every public export against accepted complete-label origins, no fit/env."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from audit_rl_execution import read_json,require,sha256
from audit_g1_headroom import decoded


def audit(campaign,collection,dataset,label_audit):
    campaign,collection,dataset,label_audit=(Path(p).resolve() for p in (campaign,collection,dataset,label_audit))
    require(collection.is_relative_to(campaign) and dataset.is_relative_to(campaign),'Out-of-round export')
    sys.path.insert(0,str(campaign.parent))
    from training_round1_20260912.features import build_snapshot,validate_snapshot
    sources={}
    def read(path):
        sources[str(path)]=sha256(path)
        return read_json(path)
    accepted=read(label_audit)
    require(accepted['status']=='complete_shared_first_round_labels_verified','Labels are not independently audited')
    for path, expected in accepted['source_sha256'].items():
        require(sha256(path)==expected,'Previously audited label artifact changed')
        sources[path]=expected
    def read_label(path):
        path=path.resolve()
        require(path.is_relative_to(collection) and str(path) in accepted['source_sha256']
                and sha256(path)==accepted['source_sha256'][str(path)], 'Export origin is not an independently accepted label artifact')
        return read(path)
    for name in ('features.py','export_fit.py'):
        sources[str(campaign/name)]=sha256(campaign/name)
    manifest=read(dataset/'manifest.json');summary=read_label(collection/'summary.json')
    worlds=read_label(collection/'world_results.json')['worlds']
    require(set(manifest)=={'schema','worlds','counts','state_bundles','nonreference_labels','teacher_only_states','zero_state_worlds',
        'label_scale','continuation_policy_sha256','shared_for_three_independent_initializations','trusted_exporter_sha256',
        'feature_implementation_sha256','source_collection_summary_sha256','source_world_results_sha256','read_boundary'}
        and manifest['schema']=='bc-rpi-round1-public-fit-manifest-v1' and manifest['counts']=={'fit':24,'fit_val':12}
        and manifest['label_scale']==.002 and manifest['shared_for_three_independent_initializations'] is True,
        'Public manifest contract differs from the fixed fitter input')
    require(manifest['source_collection_summary_sha256']==sha256(collection/'summary.json')
            and manifest['source_world_results_sha256']==sha256(collection/'world_results.json')
            and manifest['feature_implementation_sha256']==sha256(campaign/'features.py')
            and manifest['trusted_exporter_sha256']==sha256(campaign/'export_fit.py')
            and manifest['continuation_policy_sha256']==summary['continuation_policy_sha256'], 'Public dataset provenance mismatch')
    require(len(manifest['worlds'])==len(worlds)==36,'Incomplete public population')
    counts=Counter();seen=set()
    for entry, original in zip(manifest['worlds'],worlds):
        require(set(entry)=={'role','world_id','world_sha256','path','sha256','states'},'Unexpected public index fields')
        require(all(entry[k]==original[k] for k in ('world_id','world_sha256','role')),'Public world order/role identity changed')
        path=(dataset/entry['path']).resolve()
        require(path.parent==dataset and sha256(path)==entry['sha256'],'Public world path/hash mismatch')
        world=read(path)
        require(set(world)=={'schema','world_id','world_sha256','role','states','state_count','complete','no_world_truth','empty_state_and_world_weight'},'Unexpected world export fields')
        require(world['schema']=='bc-rpi-round1-public-fit-world-v1'
                and world['empty_state_and_world_weight']=='retained with zero loss','Public world schema/weight convention changed')
        require(all(world[k]==entry[k] for k in ('world_id','world_sha256','role')) and world['complete'] is True
                and world['no_world_truth'] is True and world['world_id'] not in seen,'Invalid or repeated public world')
        seen.add(world['world_id']);counts[world['role']]+=1
        require(len(world['states'])==world['state_count']==entry['states']==original['state_count'],'Changed state denominator')
        counts['zero_state_worlds']+=not world['states']
        for state, source in zip(world['states'],original['states']):
            require(set(state)=={'snapshot','targets_normalized','teacher_index','origin_run_ids','reference_origin_run_id','choice_id','source_index','state_index','complete_bundle','continuation_policy_sha256'},'Unexpected state export fields')
            bundle=read_label(campaign/source['path']);handle=read_label(campaign/source['handle_path'])
            # PreparedChoice is plain JSON; its embedded controller and the
            # token's public event state retain their canonical tagged form.
            prepared=handle['prepared'];token=handle['token']
            public=decoded(token['interface_public_state'])
            expected=build_snapshot(prepared,public['events'])
            validate_snapshot(state['snapshot'])
            require(state['snapshot']==expected,'Export features differ from the accepted public handle')
            ids=expected['candidate_ids'];teacher=expected['teacher_id'];ref=ids.index(teacher)
            origins=[r['run_id'] for r in bundle['outcomes']]
            require(state['targets_normalized']==[r['paired_gain_to_A0'] for r in bundle['outcomes']]
                    and state['origin_run_ids']==origins and state['reference_origin_run_id']==origins[ref]
                    and state['teacher_index']==ref and state['complete_bundle'] is True
                    and all(state[k]==bundle[k] for k in ('choice_id','source_index','state_index','continuation_policy_sha256')),
                    'Exported labels/origins not aligned to complete retained candidate bundle')
            counts['state_bundles']+=1;counts['nonreference_labels']+=len(ids)-1;counts['teacher_only_states']+=len(ids)==1
    require(counts['fit']==24 and counts['fit_val']==12,'Training/validation partition changed')
    for key in ('state_bundles','nonreference_labels','teacher_only_states','zero_state_worlds'):
        require(manifest[key]==counts[key],'Public count differs: '+key)
    require(set(dataset.glob('*.json.gz'))=={dataset/e['path'] for e in manifest['worlds']},'Extra/missing public dataset files')
    require(all(sha256(p)==s for p,s in sources.items()),'Evidence changed during export audit')
    return dict(schema='bc-rpi-r1-public-export-independent-audit-v1',status='all_public_features_labels_and_origins_verified',
        counts=dict(counts),dataset_manifest_sha256=sha256(dataset/'manifest.json'),source_sha256=sources,
        auditor_sha256=sha256(__file__),actual_environment_calls=0,actual_optimizer_updates=0,
        evidence_limits=['Accepted feature implementation reused; every tensor rederived from public saved handle.',
            'World identifiers remain provenance metadata and are not model tensor inputs.'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('campaign','collection','dataset','label-audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();require(not a.out.exists(),'Preserve prior audit')
    result=audit(a.campaign,a.collection,a.dataset,a.label_audit)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','counts')},indent=2))
