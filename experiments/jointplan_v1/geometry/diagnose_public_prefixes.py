"""Pure proposal diagnostics on detached public observations, no environment."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from experiments.jointplan_v1.geometry import propose, snapshot_hash, verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshots', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    snapshots = json.loads(args.snapshots.read_text())
    spec = {'role': 'public-prefix candidate-space diagnostics only', 'environment_calls': 0,
            'input_sha256': hashlib.sha256(args.snapshots.read_bytes()).hexdigest(),
            'geometry_sha256': {name: hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('engine.py', 'continuous.py')},
            'variants': {'3': [{'block_sizes': [count], 'max_plans': 2, 'max_seconds': .75, 'prune_channels': True} for count in (2, 3, 4)],
                         '4': [{'block_sizes': [count], 'max_plans': 2, 'max_seconds': 1.5, 'prune_channels': True, 'step_scale': .05 if count == 2 else .005} for count in (2, 3, 4)]},
            'max_plans_per_prefix': 6, 'actual_future_outcomes_observed': False}
    (args.out/'SPEC.json').write_text(json.dumps(spec, indent=2))
    all_rows = []
    started = time.perf_counter()
    with (args.out/'prefixes.jsonl').open('w') as stream:
        for i, snapshot in enumerate(snapshots):
            if snapshot_hash(snapshot) != snapshot['snapshot_hash']:
                raise ValueError('public hash mismatch')
            row = {'snapshot_hash': snapshot['snapshot_hash'], 'mode': snapshot['mode'], 'history_version': snapshot['history_version'], 'station_count': len(snapshot['stations']), 'source_task_count': len(snapshot['source_tasks']), 'unknown_channel_count': len(snapshot['unknown_channels']), 'variants': []}
            for options in spec['variants'][str(snapshot['mode'])]:
                diagnostics = {}
                plans = propose(snapshot, options, diagnostics)
                for plan in plans:
                    recheck = verify(snapshot, plan)
                    if recheck['status'] != 'certified':
                        raise ValueError('emitted candidate did not independently reverify')
                    plan['diagnostic_id'] = str(options['block_sizes'][0]) + ':' + str(len(row['variants'])) + ':' + str(plans.index(plan))
                row['variants'].append({'options': options, 'diagnostics': diagnostics, 'plans': plans})
            stream.write(json.dumps(row, sort_keys=True) + '\n')
            stream.flush()
            all_rows.append(row)
            if (i + 1) % 8 == 0:
                print(json.dumps({'completed_prefixes': i + 1, 'total_prefixes': len(snapshots), 'wall_s': time.perf_counter() - started}), flush=True)
    summary = {'environment_calls': 0, 'wall_s': time.perf_counter() - started, 'groups': {}}
    for mode in (3, 4):
        rows = [r for r in all_rows if r['mode'] == mode]
        variants = [v for r in rows for v in r['variants']]
        plans = [p for v in variants for p in v['plans']]
        summary['groups'][str(mode)] = {'prefixes': len(rows), 'prefixes_with_any_plan': sum(any(v['plans'] for v in r['variants']) for r in rows), 'plans': len(plans), 'block_sizes': {str(n): {'variants': sum(v['options']['block_sizes'] == [n] for v in variants), 'variants_with_plan': sum(v['options']['block_sizes'] == [n] and bool(v['plans']) for v in variants), 'plans': sum(len(v['plans']) for v in variants if v['options']['block_sizes'] == [n])} for n in (2, 3, 4)}, 'mean_generation_s': statistics.mean(v['diagnostics']['seconds'] for v in variants), 'max_generation_s': max(v['diagnostics']['seconds'] for v in variants), 'status_counts': dict(sum((collections.Counter(v['diagnostics']['statuses']) for v in variants), collections.Counter())), 'mean_positive_coordinate_proxy_gain_s': statistics.mean(p['coordinate_gain_same_order_s'] for p in plans) if plans else None, 'max_coordinate_proxy_gain_s': max((p['coordinate_gain_same_order_s'] for p in plans), default=None), 'deleted_paid_channel_actions': sum(len(p['removed_channel_actions']) for p in plans)}
    (args.out/'SUMMARY.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
