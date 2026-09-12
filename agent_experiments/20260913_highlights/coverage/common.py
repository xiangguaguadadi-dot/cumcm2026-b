"""Scoped coverage experiment utilities; no decision access to world truth."""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = ROOT / '最佳方法/代码/solver.py'
PARENT_SHA = 'e6a0666d644ceaa1d7ae69f19042b9ca022379f3e5a57d927e52bcf1a09360bd'
CERT = ROOT / 'experiments/B3/research/certificate_21_999_1864.json'
CERT_SHA = '8eaeae3c86cd7378ef4a242afdae2ba35d3620ba0c82cf9419ab5ebdb4cdeaba'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def frozen_check():
    manifest = json.loads((ROOT/'evaluation/manifest_v1.json').read_text())
    mismatches = [p for p, h in manifest['sha256'].items() if sha(ROOT/p) != h]
    assert not mismatches, mismatches
    assert sha(PARENT) == PARENT_SHA
    assert sha(CERT) == CERT_SHA
    return dict(manifest_sha256=sha(ROOT/'evaluation/manifest_v1.json'),
                parent_sha256=sha(PARENT), certificate_sha256=sha(CERT),
                files_verified=len(manifest['sha256']), mismatches=mismatches)


def points21():
    return [tuple(p) for p in json.loads(CERT.read_text())['points']]


def points22():
    r = 999.5
    inner = [(r*math.cos(2*math.pi*k/7), r*math.sin(2*math.pi*k/7)) for k in range(7)]
    outer = [(2*x, 2*y) for x, y in inner]
    mids = [(inner[k][0]+inner[(k+1)%7][0], inner[k][1]+inner[(k+1)%7][1]) for k in range(7)]
    return [(0., 0.)] + inner + outer + mids


class NoActions:
    def __getattr__(self, name):
        raise AssertionError('Unexpected environment action during construction: '+name)


def initial_registration():
    frozen = frozen_check()
    return dict(
        task='B: continuous half-plane coverage and existence/termination certificates',
        created_utc=subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], text=True).strip(),
        python=platform.python_version(), executable=sys.executable,
        parent=str(PARENT.relative_to(ROOT)), **frozen,
        physical_source_sha256=sha(ROOT/'local_env.py'),
        cases_sha256=sha(ROOT/'evaluation/cases_v1.json'),
        source_restriction='Solver sees only enter/measure/clear/exit; evaluation reads truth.',
        arms=['fixed21', 'fixed22', 'rotating21', 'pure21', 'pure22'],
        primary_comparison='fixed21 minus fixed22 on same Q4 full-v1 cases',
        secondary_comparison='rotating21 minus fixed21; separate from layout comparison',
        full_v1=dict(mode=4, worlds=1200, sources_per_world='frozen 10..16',
                     arms=['fixed21', 'fixed22', 'rotating21'], policy_executions=3600,
                     role='exposed local regression, no holdout'),
        quick_v1=dict(mode=4, worlds=60, arms=3, policy_executions=180,
                      subset_of_full=True),
        stopping='No tuning from result; preserve failures. All arms must complete before speed ranking.',
        pure_geometry='Disable stop_discovered, upper_bound_stop, all_sources_discovered and final count certificate; keep pending-source clearing.',
        scope='No changes outside this coverage directory; no official simulator, training, or blind-test claim.',
    )
