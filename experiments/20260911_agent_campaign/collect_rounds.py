"""Collect every saved full round, including rejected candidates, for reporting."""
from __future__ import annotations

import hashlib
import json
import re
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent


def collect():
    assignments = json.loads((HERE / 'assignments.json').read_text())['assignments']
    records = []
    for assignment in assignments:
        root = Path(assignment['worktree'])
        identity = assignment['id']
        paths = list(root.glob(f'results/{identity}_r*_full/summary.json'))
        paths += list(root.glob(f'experiments/{identity}/results/r*_full/summary.json'))
        paths.sort(key=lambda p: int(re.search(r'(?:_|/)r(\d+)_full', str(p)).group(1)))
        for summary_path in paths:
            summary = json.loads(summary_path.read_text())
            all_rows = json.loads((summary_path.parent / 'case_metrics.json').read_text())
            candidate = [r for r in all_rows if r['variant'] == 'candidate']
            baseline = {r['case_id']: r for r in all_rows if r['variant'] == 'frozen_baseline'}
            assert len(candidate) == len(baseline) == 2400
            assert len({r['case_id'] for r in candidate}) == len(candidate)
            assert set(baseline) == {r['case_id'] for r in candidate}
            modes = []
            for mode in (3, 4):
                part = [r for r in candidate if r['mode'] == mode]
                valid = all(r['complete'] and baseline[r['case_id']]['complete'] for r in part)
                info = dict(mode=mode, cases=len(part), complete=sum(r['complete'] for r in part),
                            errors=sum(bool(r['error']) for r in part), comparison_valid=valid)
                if valid:
                    b = statistics.mean(baseline[r['case_id']]['average_clear_time_s'] for r in part)
                    c = statistics.mean(r['average_clear_time_s'] for r in part)
                    info.update(baseline_mean_s_per_source=b, candidate_mean_s_per_source=c,
                                reduction_fraction=1-c/b)
                modes.append(info)
            quick = summary_path.parent.with_name(summary_path.parent.name.replace('_full', '_quick'))
            qs = json.loads((quick / 'summary.json').read_text()) if (quick / 'summary.json').is_file() else None
            records.append(dict(
                agent=identity, round=int(re.search(r'(?:_|/)r(\d+)_full', str(summary_path)).group(1)),
                candidate_sha256=summary['candidate_sha256'],
                manifest_sha256=summary['manifest_sha256'],
                full_path=str(summary_path.parent),
                full_rows_sha256=hashlib.sha256((summary_path.parent / 'case_metrics.json').read_bytes()).hexdigest(),
                full_candidate_runs=summary['runs'], full_wall_s=summary['wall_seconds'],
                quick_path=str(quick), quick_candidate_runs=qs['runs'] if qs else None,
                quick_wall_s=qs['wall_seconds'] if qs else None, modes=modes))
    return dict(note='All completed saved full rounds, including rejected candidates. '
                     'Quick is a subset of full. Baseline cache is not counted as a fresh run.',
                full_rounds=len(records), full_candidate_runs=sum(r['full_candidate_runs'] for r in records),
                quick_candidate_runs=sum(r['quick_candidate_runs'] or 0 for r in records), rounds=records)


if __name__ == '__main__':
    result = collect()
    (HERE / 'all_rounds.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != 'rounds'}, ensure_ascii=False))
