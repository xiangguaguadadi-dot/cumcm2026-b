"""Run exactly the two predeclared frozen packages on reserved local cases.

The outcomes do not select a new candidate. Both complete raw row files are
kept, including failures, and the audit pairs by case ID and shared seed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def committed(path):
    path = Path(path).resolve()
    rel = path.relative_to(ROOT).as_posix()
    return subprocess.check_output(['git', 'show', 'HEAD:' + rel], cwd=ROOT) == path.read_bytes()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--registry', type=Path, required=True)
    a = p.parse_args()
    reg = read(a.registry)
    assert committed(a.registry), 'Commit the final registration before reading outcomes'
    assert reg['research_frozen'] is True
    assert set(reg['agents_frozen']) == {'a1', 'a2', 'a3'}
    assert reg['confirmation_policy'] == 'one paired confirmation; no outcome-dependent candidate revision'
    assert [c['role'] for c in reg['candidates']] == ['start_baseline', 'frozen_candidate']
    required_files = {reg['cases'], reg['seed_review'],
        'experiments/20260911_stage3/final_review.py', 'evaluate.py', 'local_env.py',
        'evaluation/manifest_v1.json',
        str((HERE / 'audit_pair.py').relative_to(ROOT)),
        str(Path(__file__).resolve().relative_to(ROOT)),
        str((HERE / 'review_confirmation_seeds.py').relative_to(ROOT)),
        *(c['path'] for c in reg['candidates'])}
    assert required_files <= set(reg['frozen_files']), 'Incomplete frozen execution identity'
    for name, digest in reg['frozen_files'].items():
        target = ROOT / name
        assert sha(target) == digest, 'Changed frozen file: ' + name
        assert committed(target), 'Uncommitted frozen file: ' + name
    # Both strategies must be committed before reading a case or running a
    # baseline. A later failure cannot leave an uncommitted candidate selectable
    # after the first outcome has already been observed.
    for candidate in reg['candidates']:
        path = ROOT / candidate['path']
        assert sha(path) == candidate['sha256'] and committed(path)
    cases_path = ROOT / reg['cases']
    cases = read(cases_path)
    helper = module('campaign_final_helper', ROOT / 'experiments/20260911_stage3/final_review.py')
    helper.validate_cases(cases)
    assert sha(cases_path) == reg['cases_sha256']
    exclusion = read(ROOT / reg['seed_review'])
    assert exclusion['overlap'] == [] and exclusion['confirmation_seeds'] == sorted({c['seed'] for c in cases})
    out = ROOT / reg['output']
    out.mkdir(parents=True, exist_ok=False)
    summaries = []
    for candidate in reg['candidates']:
        path = ROOT / candidate['path']
        assert sha(path) == candidate['sha256'] and committed(path)
        summaries.append(helper.execute(path, {}, cases_path, out / candidate['role'],
            candidate['label'], candidate['role'], extra_identity={'registry_sha256': sha(a.registry)},
            data_role='parallel_v2_reserved_new_seed_confirmation_local'))
    audit = module('campaign_pair_audit', HERE / 'audit_pair.py')
    result = audit.compare(read(out / 'frozen_candidate/case_metrics.json'),
                           read(out / 'start_baseline/case_metrics.json'), cases)
    result.update(registry_sha256=sha(a.registry), cases_sha256=sha(cases_path),
                  note='Fresh seeds from the same assumed local distributions; no official execution.')
    (out / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    for name, digest in reg['frozen_files'].items():
        assert sha(ROOT / name) == digest
    print(json.dumps({'runs': sum(s['actual_runs'] for s in summaries),
        'all_complete': result['all_complete'],
        'modes': [r for r in result['comparisons'] if r['group'] == 'ALL']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
