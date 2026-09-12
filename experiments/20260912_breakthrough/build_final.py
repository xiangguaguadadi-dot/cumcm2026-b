"""Mechanically embed two immutable task-wise candidates; no policy tuning."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--q3', type=Path, required=True)
    p.add_argument('--q3-sha', required=True)
    p.add_argument('--q4', type=Path, required=True)
    p.add_argument('--q4-sha', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    q3, q4 = a.q3.resolve(), a.q4.resolve()
    assert q3.is_relative_to(HERE / 'A1')
    assert q4.is_relative_to(HERE / 'A2')
    assert sha(q3) == a.q3_sha and sha(q4) == a.q4_sha
    assert not a.out.exists()
    assert not (a.out.parent / 'coverage_points.json').exists()
    source = '''"""Task-wise retained Q3/Q4; self-contained, no learned policy."""
import types
from pathlib import Path as _DeploymentPath
if _DeploymentPath(__file__).with_name('coverage_points.json').exists():
    raise RuntimeError('Frozen deployment requires no adjacent coverage_points.json')
'''
    for name, path in [('_FINAL_Q3', q3), ('_FINAL_Q4', q4)]:
        body = path.read_text()
        compile(body, str(path), 'exec')
        source += f'{name}=types.ModuleType({name!r})\n{name}.__file__=__file__\n'
        source += f'exec(compile({body!r},__file__+{name!r},"exec"),{name}.__dict__)\n'
    source += '''
BASELINE_CONFIG=dict(_FINAL_Q3.BASELINE_CONFIG)
OPTIMIZED_CONFIGS={3:dict(_FINAL_Q3.OPTIMIZED_CONFIGS[3]),4:dict(_FINAL_Q4.OPTIMIZED_CONFIGS[4])}
class Solver:
    def __new__(cls,env,mode=3,**config):
        if mode not in (3,4):raise ValueError('mode must be 3 or 4')
        selected=_FINAL_Q3 if mode==3 else _FINAL_Q4
        return selected.Solver(env,mode=mode,**config)
'''
    compile(source, str(a.out), 'exec')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(source)
    manifest = dict(build='mechanical task-wise dispatch; not an optimization round',
        q3_source=str(q3.relative_to(HERE)), q3_sha256=sha(q3),
        q4_source=str(q4.relative_to(HERE)), q4_sha256=sha(q4),
        candidate=str(a.out), candidate_sha256=sha(a.out),
        builder_sha256=sha(__file__), external_deployment_dependencies=[],
        deployment_preconditions=['No adjacent coverage_points.json; fail-closed at import'],
        validation_status='not yet executed')
    a.out.with_suffix('.build.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
