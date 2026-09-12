"""Source archive backfill and non-mutating aggregation of all G0 evidence."""
import hashlib
from pathlib import Path
from .budget import IMPL
from .runtime import load,save_new
from .source_archive import archive_sources
from ..deploy.vendor import REPO,implementation_hash


def finalize():
    stages=['g0_v1','g0_v2','g0_v2_resume1','g0_partial_override_v1']
    archives=[]
    for name in stages:
        stage=IMPL/'results'/name;freeze=load(stage/'source_freeze.json')
        if not (stage/'sources.zip').exists():
            overrides={}
            for relative,expected in freeze['files'].items():
                data=(REPO/relative).read_bytes()
                if hashlib.sha256(data).hexdigest()!=expected:
                    # The only known v1 change was output path normalization.
                    candidate=data.replace(b'    out=Path(out).resolve()\n    out.relative_to(IMPL)  # Only the authorized implementation output tree.\n',b'    out=Path(out)\n')
                    if name!='g0_v1' or hashlib.sha256(candidate).hexdigest()!=expected:
                        raise RuntimeError('Original recorded source bytes are unavailable: '+relative)
                    overrides[relative]=candidate
            archive=archive_sources(freeze,stage/'sources.zip',overrides=overrides,
                provenance='archived_after_execution; every byte hash checked against original pre-execution freeze; v1 path-only reverse patch explicitly marked')
            save_new(stage/'source_archive.json',archive)
        archives.append(dict(stage=name,**load(stage/'source_archive.json')))
    out=IMPL/'results/g0_final'
    if out.exists():raise FileExistsError('Immutable final aggregate already exists')
    out.mkdir()
    rows=[];checks=[]
    for stage_name in ('g0_v2_resume1','g0_partial_override_v1'):
        stage=IMPL/'results'/stage_name
        for row in load(stage/'index.json')['runs']:
            rows.append(dict(row,origin_run_id=row.get('origin_run_id',row['run_id']),
                origin_path=row.get('origin_path',row['path']),
                origin_source_freeze=row.get('origin_source_freeze',str((stage/'source_freeze.json').relative_to(IMPL))),
                aggregate_only_new_calls=0,aggregate_only_new_executions=0))
        checks+=load(stage/'fixture_checks.json')['checks']
    if len(rows)!=141 or len({r['run_id'] for r in rows})!=141:
        raise RuntimeError('Unexpected G0 aggregate run cardinality')
    if not all(c['pass_'] for c in checks):raise RuntimeError('A G0 check still fails')
    save_new(out/'index.json',dict(schema='bc-rpi-g0-run-index-v1',runs=rows,
        aggregation='141 unique accepted G0 evidence runs; excludes only first completed original run followed by output-path failure, whose cost and raw result remain in campaign ledger',
        non_gate_historical_runs=['g0_v1_q3_w00_original_c7']))
    pairs=load(IMPL/'results/g0_v2_resume1/equivalence.json')
    save_new(out/'equivalence.json',pairs)
    save_new(out/'fixture_checks.json',dict(checks=checks))
    save_new(out/'source_archives.json',dict(archives=archives,
        deploy_implementation_sha256=implementation_hash()))
    status=load(IMPL/'execution_status.json')
    save_new(out/'summary.json',dict(status='g0_complete_pending_coordinator_acceptance',
        paired_c7_worlds=48,paired_latest_q3_worlds=12,extra_real_fixture_executions=21,
        unique_gate_evidence_runs=len(rows),all_checks_pass=True,check_count=len(checks),
        actual_world_content_hashes=len({r['metadata']['world_sha256'] for r in status['runs']}),
        cumulative_actual_business_calls=status['business_calls'],accepted_calls=status['accepted_calls'],
        known_rejected_calls=status['rejected_calls'],unknown_cost_calls=status['unknown_cost_calls'],
        executions_started=status['executions_started'],executions_completed=status['executions_completed'],
        full_runs=status['full_runs'],suffix_runs=status['suffix_runs'],fixture_runs=status['fixture_runs'],
        outstanding_run=status['current_run'],network_training_runs=0,g1_worlds_executed=0,official_runs=0,
        timing_comparer_amendment='Latest Q3 only: remove counters.a1_cover_cpu_s for equality; every raw value and prior failure retained',
        expected_real_failure='after_deadline suffix: one known LocalEnv rejection, no unknown acceptance',
        historical_engineering_error='g0_v1 output-path failure after 142 known accepted C7 calls; cost never removed',
        evidence_boundary='G0 checks correctness/interfaces only. No action-space headroom, network learning, OOD, sealed-final or official success claim.'))
    print(str(out))


if __name__=='__main__':finalize()
