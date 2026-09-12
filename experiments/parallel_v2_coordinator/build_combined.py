"""Package two already frozen, self-contained mode implementations."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def build(q3: Path, q4: Path, out: Path) -> dict:
    assert not out.exists(), 'Keep prior packages immutable'
    source = ['"""Mode dispatch only; parent implementations are embedded unchanged."""', 'import types']
    parents = {}
    for name, path in [('Q3', q3), ('Q4', q4)]:
        data = path.read_bytes()
        parents[name] = {'path': str(path.resolve()), 'sha256': hashlib.sha256(data).hexdigest()}
        source += [f'_{name} = types.ModuleType("frozen_{name}")',
                   f'_{name}.__file__ = __file__',
                   f'exec(compile({data.decode()!r}, __file__ + ":{name}", "exec"), _{name}.__dict__)']
    source += ['BASELINE_CONFIG = dict(_Q3.BASELINE_CONFIG)',
               'OPTIMIZED_CONFIGS = {3: dict(_Q3.OPTIMIZED_CONFIGS[3]), 4: dict(_Q4.OPTIMIZED_CONFIGS[4])}',
               'class Solver:',
               '    def __new__(cls, env, mode=3, **config):',
               '        if mode not in (3, 4): raise ValueError("mode must be 3 or 4")',
               '        parent = _Q3 if mode == 3 else _Q4',
               '        return parent.Solver(env, mode=mode, **config)', '']
    text = '\n'.join(source)
    compile(text, str(out), 'exec')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    manifest = {'operation': 'mode dispatch; neither parent source changed', 'parents': parents,
                'candidate_sha256': hashlib.sha256(out.read_bytes()).hexdigest(), 'dependencies': {}}
    out.with_suffix('.provenance.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--q3', type=Path, required=True)
    parser.add_argument('--q4', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.q3, args.q4, args.out), ensure_ascii=False))
