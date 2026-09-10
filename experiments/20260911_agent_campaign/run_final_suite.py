"""Run the frozen registry on one immutable new-case file in isolated processes."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    registry = json.loads((HERE/'candidate_registry.json').read_text())
    root = HERE/'final_validation'
    manifest = json.loads((root/'manifest.json').read_text())
    assert sha(root/'cases.json') == manifest['cases_sha256']
    assert sha(HERE/'final_review.py') == registry['review_script_sha256'] == manifest['review_script_sha256']
    assert sha(ROOT/registry['baseline_path']) == registry['baseline_sha256']
    entries = [dict(label='baseline', candidate_path=registry['baseline_path'],
                    candidate_sha256=registry['baseline_sha256'], baseline=True)]
    entries += [{**item, 'baseline':False} for item in registry['candidates']]
    for entry in entries:
        assert sha(ROOT/entry['candidate_path']) == entry['candidate_sha256']
        assert not (root/entry['label']).exists()
    logdir = root/'process_logs'
    logdir.mkdir(exist_ok=False)
    start=time.perf_counter()
    metadata=dict(started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        workers=2, scheduling='registry order, at most two independent evaluator processes',
        runtime_note='Concurrent same-host load; measured real runtime is not a controlled speed comparison.',
        registry_sha256=sha(HERE/'candidate_registry.json'), cases_sha256=sha(root/'cases.json'),
        final_review_sha256=sha(HERE/'final_review.py'), results=[])
    (root/'execution.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))

    def run(entry):
        command=[sys.executable,str(HERE/'final_review.py'),'run','--root',str(ROOT),
            '--candidate',str(ROOT/entry['candidate_path']),'--cases',str(root/'cases.json'),
            '--out',str(root/entry['label']),'--label',entry['label']]
        if entry['baseline']:
            command.append('--baseline')
        with (logdir/(entry['label']+'.log')).open('w') as stream:
            result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        assert result.returncode == 0, entry['label']+' evaluator process failed; inspect saved log'
        data=json.loads((root/entry['label']/'summary.json').read_text())
        assert data['candidate_sha256']==entry['candidate_sha256']
        return dict(label=entry['label'],wall_seconds=data['wall_seconds'],
                    valid_completion=data['all_valid_completion'],
                    means=[m['mean_s_per_source'] for m in data['modes']])

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures=[executor.submit(run,entry) for entry in entries]
        for future in concurrent.futures.as_completed(futures):
            info=future.result();metadata['results'].append(info)
            print(json.dumps(info,ensure_ascii=False),flush=True)
    assert sha(root/'cases.json')==metadata['cases_sha256']
    assert sha(HERE/'candidate_registry.json')==metadata['registry_sha256']
    assert sha(HERE/'final_review.py')==metadata['final_review_sha256']
    metadata.update(finished_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                    suite_wall_seconds=time.perf_counter()-start,processes=len(entries),
                    total_episode_executions=len(entries)*manifest['cases'])
    (root/'execution.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    command=[sys.executable,str(HERE/'final_review.py'),'compare',
       '--baseline-rows',str(root/'baseline/case_metrics.json'),'--candidate-rows']
    command += [str(root/entry['label']/'case_metrics.json') for entry in entries if not entry['baseline']]
    command += ['--out',str(root/'comparison.json')]
    with (logdir/'comparison.log').open('w') as stream:
        subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=True)
    print(json.dumps(dict(comparison_complete=True,episodes=metadata['total_episode_executions'],
                         wall_seconds=metadata['suite_wall_seconds'])),flush=True)


if __name__ == '__main__':
    main()
