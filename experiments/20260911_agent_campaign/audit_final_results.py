"""Independently check final saved rows against case and candidate identities."""
from __future__ import annotations

import collections
import hashlib
import json
import math
import statistics
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    directory=HERE/'final_validation'
    registry=read(HERE/'candidate_registry.json')
    manifest=read(directory/'manifest.json')
    execution=read(directory/'execution.json')
    cases=read(directory/'cases.json')
    index={c['case_id']:c for c in cases}
    assert len(index)==len(cases)==2400
    assert registry['registered_at_utc']<manifest['generation_time_utc']
    assert sha(directory/'cases.json')==manifest['cases_sha256']==execution['cases_sha256']
    assert sha(HERE/'candidate_registry.json')==execution['registry_sha256']
    assert sha(HERE/'final_review.py')==manifest['review_script_sha256']==registry['review_script_sha256']
    assert sha(ROOT/'solver.py')==registry['baseline_sha256']
    frozen=read(ROOT/'evaluation/manifest_v1.json')['sha256']
    assert all(sha(ROOT/name)==expected for name,expected in frozen.items())
    seeds={c['seed'] for c in cases}
    assert len(seeds)==100 and not seeds.intersection(range(5000,5100))
    group_counts=collections.Counter((c['mode'],c['group']) for c in cases)
    assert len(group_counts)==24 and set(group_counts.values())=={100}
    for case in cases:
        sources=case['sources'];assert 10<=len(sources)<=16
        assert len({s['channel'] for s in sources})==len(sources)
        for source in sources:
            assert 1<=source['channel']<=20
            assert math.hypot(source['x'],source['y'])<=1800+1e-8
            assert 1000<=source['radius']<=1500
            assert source['cleared'] is False
        types=sum(s['direction'] is not None for s in sources)
        assert types==0 if case['mode']==3 else 0<types<len(sources)
    expected=[dict(label='baseline',candidate_path=registry['baseline_path'],candidate_sha256=registry['baseline_sha256'])]+registry['candidates']
    assert execution['processes']==len(expected)==11
    comparisons={Path(c['path']).parent.name:c for c in read(directory/'comparison.json')['candidates']}
    baseline={r['case_id']:r for r in read(directory/'baseline/case_metrics.json')}
    outputs=[]
    for item in expected:
        label=item['label'];summary=read(directory/label/'summary.json')
        rows=read(directory/label/'case_metrics.json')
        assert len(rows)==len({r['case_id'] for r in rows})==2400
        assert {r['case_id'] for r in rows}==set(index)
        assert sha(ROOT/item['candidate_path'])==summary['candidate_sha256']==item['candidate_sha256']
        assert summary['optional_coverage_sha256'] is None and summary['selected_dependencies']=={}
        assert summary['cases_sha256']==manifest['cases_sha256']
        assert summary['review_script_sha256']==registry['review_script_sha256']
        assert summary['manifest_sha256']==registry['frozen_manifest_sha256']
        modes=[]
        for r in rows:
            c=index[r['case_id']]
            assert r['mode']==c['mode'] and r['group']==c['group'] and r['seed_cluster']==c['seed']
            assert r['source_count']==len(c['sources'])==r['cleared_count']
            assert r['complete'] and r['cleared_fraction']==1 and not r['error']
            assert r['exit_reason']=='user_exit'
            assert r['total_virtual_time_s']<360000 and r['program_runtime_s']<1200
            assert abs(r['average_clear_time_s']-r['total_virtual_time_s']/r['cleared_count'])<1e-8
        for mode in (3,4):
            part=[r for r in rows if r['mode']==mode]
            assert len(part)==1200
            average=statistics.mean(r['average_clear_time_s'] for r in part)
            summary_mode=next(m for m in summary['modes'] if m['mode']==mode)
            assert abs(average-summary_mode['mean_s_per_source'])<1e-8
            differences=[baseline[r['case_id']]['average_clear_time_s']-r['average_clear_time_s'] for r in part]
            if label!='baseline':
                reported=next(m for m in comparisons[label]['modes'] if m['mode']==mode)
                assert reported['comparison_valid'] and reported['seed_clusters']==100
                assert abs(statistics.mean(differences)-reported['paired_mean_saved_s_per_source'])<1e-8
            modes.append(dict(mode=mode,complete=1200,sources=sum(r['source_count'] for r in part),
                mean_s_per_source=average,wins=sum(d>1e-8 for d in differences),
                ties=sum(abs(d)<=1e-8 for d in differences),losses=sum(d<-1e-8 for d in differences),
                maximum_total_virtual_s=max(r['total_virtual_time_s'] for r in part),
                maximum_runtime_s=max(r['program_runtime_s'] for r in part)))
        outputs.append(dict(label=label,modes=modes,rows_sha256=sha(directory/label/'case_metrics.json'),
                            summary_sha256=sha(directory/label/'summary.json')))
    result=dict(status='all_checks_passed',candidates=10,baseline_versions=1,case_count=2400,
        episode_executions=26400,all_q4_cases_mixed=True,all_cases_complete_normal_no_errors=True,
        cases_sha256=manifest['cases_sha256'],registry_sha256=sha(HERE/'candidate_registry.json'),
        registry_commit=subprocess.check_output(['git','-C',str(ROOT),'log','-1','--format=%H','--',str(HERE/'candidate_registry.json')],text=True).strip(),
        source_counts_by_mode={str(m):sum(len(c['sources']) for c in cases if c['mode']==m) for m in (3,4)},
        note='Read-only audit of actual final execution rows; not an additional experiment.',versions=outputs)
    (directory/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='versions'},ensure_ascii=False))


if __name__=='__main__':
    main()
