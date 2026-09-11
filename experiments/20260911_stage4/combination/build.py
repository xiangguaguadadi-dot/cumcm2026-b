"""Compose two frozen, self-contained parents without cross-worktree imports."""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
TREES = STAGE.parents[2]

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parents = {
        'E1_R1': TREES / 'E1_refine/experiments/E1_refine/snapshots/r1_posterior.py',
        'E2_station': TREES / 'E2_refine/experiments/E2_refine/snapshots/r1_station_only.py',
    }
    expected = {
        'E1_R1': 'd3112c89a555c13b589d01f4de9aa952dc3c5d89299845e4f0e2aff21d5fbe82',
        'E2_station': 'c459591b21c192fce79d6d93a9d753f21c0ef09ba8b46d8821803d1f929d904c',
    }
    for name, path in parents.items():
        assert digest(path) == expected[name], name
    def embedded_sources(path):
        return [n.value.args[0].args[0].value for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                and isinstance(n.value.func, ast.Name) and n.value.func.id == 'exec'
                and isinstance(n.value.args[0], ast.Call)
                and isinstance(n.value.args[0].func, ast.Name)
                and n.value.args[0].func.id == 'compile']
    assert embedded_sources(parents['E1_R1']) == embedded_sources(parents['E2_station'])
    assert len(embedded_sources(parents['E1_R1'])) == 2
    target = HERE / 'snapshots'
    target.mkdir(exist_ok=True)
    metadata = {}
    for name, path in parents.items():
        dest = target / (name + '.py')
        if dest.exists():
            assert digest(dest) == expected[name]
        else:
            dest.write_bytes(path.read_bytes())
        metadata[name] = {'file': str(dest.relative_to(HERE)), 'sha256': digest(dest)}

    # These aliases refer to the identical frozen S1 geometry modules inside E1.
    e2_text = parents['E2_station'].read_text()
    node = next(n for n in ast.parse(e2_text).body
                if isinstance(n, ast.ClassDef) and n.name == 'CostDirectional')
    component = ast.get_source_segment(e2_text, node)
    assert component.count('class CostDirectional(_Q4._LensDirectional):') == 1
    component = component.replace('class CostDirectional(_Q4._LensDirectional):',
                                  'class CostDirectional(_E1.ConditionalDirectional):', 1)
    common = ('"""C1: E1 conditional route plus E2 station cost gate; self-contained."""\n'
              'import types,math\n_E1=types.ModuleType("embedded_E1_R1")\n'
              '_E1.__file__=__file__\n'
              f'exec(compile({parents["E1_R1"].read_text()!r},"<E1-R1>","exec"),_E1.__dict__)\n'
              '_Q3=_E1._P3\n_Q4=_E1._P4\n' + component + '\n')
    variants = {
        'C1_combined': {'e2_station_cost': True, 'e2_opportunity': 'parent'},
        'C1_gate_off': {'e2_station_cost': False, 'e2_opportunity': 'parent'},
        'C1_route_off': {'e2_station_cost': True, 'e2_opportunity': 'parent',
                         'conditional_discovery': 'off'},
    }
    for name, settings in variants.items():
        footer = ('OPTIMIZED_CONFIGS={3:dict(_E1.OPTIMIZED_CONFIGS[3]),'
                  f'4:dict(_E1.OPTIMIZED_CONFIGS[4],**{settings!r})}}\n'
                  'BASELINE_CONFIG=dict(_E1.BASELINE_CONFIG)\n'
                  'class Solver:\n'
                  '    def __new__(cls,env,mode=3,**config):\n'
                  '        if mode not in (3,4):raise ValueError("mode must be 3 or 4")\n'
                  '        merged={**OPTIMIZED_CONFIGS[mode],**config}\n'
                  '        if mode==3:return _Q3.Solver(env,mode=mode,**merged)\n'
                  '        return CostDirectional(env,mode=mode,**merged)\n')
        dest = target / (name + '.py')
        content = common + footer
        if dest.exists():
            assert dest.read_text() == content
        else:
            dest.write_text(content)
        metadata[name] = {'file': str(dest.relative_to(HERE)), 'sha256': digest(dest),
                          'settings': settings, 'parents': expected,
                          'deployment_dependencies': {}}
    (HERE / 'candidate_registry.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata, indent=2))

if __name__ == '__main__':
    main()
