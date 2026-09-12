"""Independent paired metric audit; does not run a strategy or tune a candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def index(rows):
    result = {r['case_id']: r for r in rows}
    assert len(result) == len(rows), 'Duplicate case IDs'
    return result


def complete(row):
    return (row.get('complete') is True and row.get('exit_reason') == 'user_exit'
            and row.get('error') is None and type(row.get('source_count')) is int
            and row['source_count'] > 0 and row.get('cleared_count') == row['source_count'])


def quantile(values, q):
    a = sorted(values)
    position = (len(a) - 1) * q
    lo = int(position)
    hi = min(lo + 1, len(a) - 1)
    return a[lo] + (position - lo) * (a[hi] - a[lo])


def compare(candidate, baseline, cases, bootstrap_repeats=2000):
    aa, bb, cc = index(candidate), index(baseline), index(cases)
    assert set(aa) == set(bb) == set(cc), 'Unpaired case IDs'
    for cid, case in cc.items():
        for row in (aa[cid], bb[cid]):
            assert (row['mode'], row['group'], row['source_count']) == (
                case['mode'], case['group'], len(case['sources'])), 'Metadata mismatch'
            n = row.get('cleared_count')
            if n:
                assert math.isclose(row['average_clear_time_s'], row['total_virtual_time_s'] / n,
                                    rel_tol=0, abs_tol=1e-8), 'Wrong seconds/source denominator'
            else:
                assert row.get('average_clear_time_s') is None, 'Zero denominator must remain null'
    all_complete = all(complete(row) for row in candidate + baseline)
    output = []
    suites = ['combined']
    if all('exposure_suite' in case for case in cases):
        suites += sorted({case['exposure_suite'] for case in cases})
    for mode in (3, 4):
        for suite in suites:
            selected = [cid for cid, c in cc.items() if c['mode'] == mode
                        and (suite == 'combined' or c['exposure_suite'] == suite)]
            for group in ['ALL', *sorted({cc[cid]['group'] for cid in selected})]:
                keys = [cid for cid in selected if group == 'ALL' or cc[cid]['group'] == group]
                if not keys:
                    continue
                rows, refs = [aa[k] for k in keys], [bb[k] for k in keys]
                good = all(complete(r) for r in rows + refs)
                summary = dict(mode=mode, suite=suite, group=group, cases=len(keys),
                               source_count=sum(len(cc[k]['sources']) for k in keys),
                               candidate_complete=sum(complete(r) for r in rows),
                               baseline_complete=sum(complete(r) for r in refs), valid_comparison=good)
                if good:
                    av = [r['total_virtual_time_s'] / r['cleared_count'] for r in rows]
                    bv = [r['total_virtual_time_s'] / r['cleared_count'] for r in refs]
                    delta = [a-b for a,b in zip(av,bv)]
                    ma, mb = statistics.fmean(av), statistics.fmean(bv)
                    summary.update(candidate_mean=ma, baseline_mean=mb, delta=ma-mb,
                                   improvement_pct=100*(mb-ma)/mb,
                                   faster=sum(x < -1e-8 for x in delta), equal=sum(abs(x) <= 1e-8 for x in delta),
                                   slower=sum(x > 1e-8 for x in delta), candidate_p95=quantile(av,.95),
                                   candidate_p99=quantile(av,.99), candidate_worst=max(av),
                                   largest_regression=max(delta), largest_improvement=min(delta),
                                   candidate_requests=sum(r['requests'] for r in rows),
                                   candidate_failed_clear_attempts=sum(r['clear_failures'] for r in rows),
                                   candidate_mean_movement_s_per_source=statistics.fmean(r['distance_m']/5/r['cleared_count'] for r in rows),
                                   candidate_max_runtime_s=max(r['program_runtime_s'] for r in rows))
                    if group == 'ALL' and suite == 'combined' and bootstrap_repeats:
                        # Preserve shared-seed dependencies across stress scenarios in exposed v1.
                        clusters = defaultdict(list)
                        for cid, d in zip(keys, delta):
                            case = cc[cid]
                            clusters[(case.get('exposure_suite','fresh'), case['seed'])].append(d)
                        values = [(sum(ds), len(ds)) for ds in clusters.values()]
                        rng = random.Random(19261203 + mode)
                        draws = []
                        for _ in range(bootstrap_repeats):
                            sample = rng.choices(values, k=len(values))
                            draws.append(sum(s for s,n in sample)/sum(n for s,n in sample))
                        summary['paired_seed_cluster_bootstrap_95pct_delta'] = [quantile(draws,.025), quantile(draws,.975)]
                        summary['bootstrap_clusters'] = len(values)
                output.append(summary)
    return dict(all_complete=all_complete, unique_cases=len(cc), formula_errors=0,
                failed_candidate_ids=[r['case_id'] for r in candidate if not complete(r)],
                failed_baseline_ids=[r['case_id'] for r in baseline if not complete(r)], comparisons=output)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('candidate_rows','baseline_rows','cases','out'):
        p.add_argument('--'+name.replace('_','-'), type=Path, required=True)
    a = p.parse_args()
    assert not a.out.exists(), 'Keep previous audit immutable'
    result = compare(*[json.loads(x.read_text()) for x in (a.candidate_rows,a.baseline_rows,a.cases)])
    result['input_sha256'] = {str(x):sha(x) for x in (a.candidate_rows,a.baseline_rows,a.cases)}
    result['script_sha256'] = sha(__file__)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({**{k:v for k,v in result.items() if k!='comparisons'},
                      'modes':[r for r in result['comparisons'] if r['suite']=='combined' and r['group']=='ALL']},ensure_ascii=False))
