"""Reproducible public-state Q3 geometry diagnostics, zero environment calls."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from experiments.jointplan_v1.geometry.compensated_arcs import propose_compensated
from experiments.jointplan_v1.geometry.engine import _base_plan, proxy_cost, verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshots', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    snapshots = json.loads(args.snapshots.read_text())
    total = collections.Counter()
    rows = []
    started = time.perf_counter()
    for snapshot in snapshots:
        if snapshot['mode'] != 3:
            continue
        base = _base_plan(snapshot)
        base_cost = proxy_cost(snapshot, base['stations'])
        candidates = propose_compensated(snapshot, base, [2, 3, 4])
        total['generated'] += len(candidates)
        good = []
        statuses = collections.Counter()
        for plan in candidates:
            cost = proxy_cost(snapshot, plan['stations'])
            same = proxy_cost(snapshot, base['stations'], cost['route'])
            gain, coordinate_gain = base_cost['total_s'] - cost['total_s'], same['total_s'] - cost['total_s']
            if gain <= 0 or coordinate_gain <= 0:
                continue
            total['positive_proxy'] += 1
            result = verify(snapshot, plan)
            total[result['status']] += 1
            statuses[result['status']] += 1
            if result['status'] == 'certified':
                good.append({'proxy_gain_s': gain, 'coordinate_gain_same_order_s': coordinate_gain,
                             'route_gain_old_geometry_s': gain-coordinate_gain, 'mechanism': plan['mechanism']})
        rows.append({'snapshot_hash': snapshot['snapshot_hash'], 'generated': len(candidates), 'statuses': dict(statuses), 'positive_certified': good})
    result = {'environment_calls': 0, 'environment_executions': 0, 'input_role': 'detached public prefixes; future observations unavailable', 'input_sha256': hashlib.sha256(args.snapshots.read_bytes()).hexdigest(), 'source_sha256': {n: hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in ('compensated_arcs.py', 'compensated_engine.py', 'engine.py', 'continuous.py')}, 'counts': dict(total), 'prefixes': len(rows), 'prefixes_with_positive_certified': sum(bool(r['positive_certified']) for r in rows), 'wall_s': time.perf_counter()-started, 'rows': rows}
    (args.out/'diagnostics.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
