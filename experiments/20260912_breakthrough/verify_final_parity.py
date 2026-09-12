"""Independent per-row task-wise packaging parity, excluding real wall clocks."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def index(path):
    rows = read(path)
    mapping = {r['case_id']: r for r in rows}
    assert len(rows) == len(mapping) == 4800
    return mapping


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--rows', type=Path, required=True)
    p.add_argument('--q3-source', type=Path, required=True)
    p.add_argument('--q4-source', type=Path, required=True)
    p.add_argument('--q3-rows', type=Path, required=True)
    p.add_argument('--q4-rows', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    assert not a.out.exists()
    final, q3, q4 = index(a.rows), index(a.q3_rows), index(a.q4_rows)
    assert final.keys() == q3.keys() == q4.keys()
    # Extract literal sources without executing the candidate.
    tree = ast.parse(a.candidate.read_text())
    embedded = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                and isinstance(n.value, str) and len(n.value) > 10000]
    assert a.q3_source.read_text() in embedded
    assert a.q4_source.read_text() in embedded
    summaries=[]
    for rows_path,source_path in [(a.rows,a.candidate),(a.q3_rows,a.q3_source),(a.q4_rows,a.q4_source)]:
        summary_path=rows_path.parent/'summary.json'
        assert read(summary_path)['candidate_sha256'] == sha(source_path)
        summaries.append(summary_path)
    fields = ['case_id','mode','group','source_count','cleared_count','cleared_fraction',
              'complete','error','exit_reason','average_clear_time_s','total_virtual_time_s',
              'requests','distance_m','clear_failures','coverage_certificate','exposure_suite']
    differences = []
    for cid, row in final.items():
        parent = (q3 if row['mode'] == 3 else q4)[cid]
        for key in fields:
            assert key in row and key in parent
            if row[key] != parent[key]:
                differences.append(dict(case_id=cid, field=key,
                                        final=row[key], parent=parent[key]))
    result = dict(status='exact_task_metric_parity' if not differences else 'mismatch',
        interpretation='4800 exposed rows, exact saved task metrics; not a full request-trace equality test',
        rows=len(final), compared_fields=fields, differences=differences,
        all_complete=all(r['complete'] and r['cleared_count']==r['source_count']
                         and r['error'] is None and r['exit_reason']=='user_exit' for r in final.values()),
        embedded_parent_sources_exact=True,
        hashes={str(path):sha(path) for path in [a.candidate,a.rows,a.q3_source,a.q4_source,
                                                a.q3_rows,a.q4_rows,*summaries,Path(__file__)]})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert not differences and result['all_complete']


if __name__ == '__main__':
    main()
