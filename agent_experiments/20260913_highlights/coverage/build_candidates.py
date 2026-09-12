"""Freeze five coverage ablations around the identical current B3 clear/localize code."""
import ast
import json
import textwrap
from common import HERE, ROOT, PARENT, PARENT_SHA, CERT, NoActions, dump, sha, load_module, initial_registration, points21, points22


def embedded_sources(source, seen=None):
    seen = set() if seen is None else seen
    if source in seen:
        return
    seen.add(source)
    yield source
    for n in ast.walk(ast.parse(source)):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'compile'
                and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
            yield from embedded_sources(n.args[0].value, seen)


def pure_run_source(source):
    candidates = []
    for nested in embedded_sources(source):
        for cls in ast.parse(nested).body:
            if isinstance(cls, ast.ClassDef) and cls.name == '_di_Solver':
                for fn in cls.body:
                    if isinstance(fn, ast.FunctionDef) and fn.name == 'run':
                        text = textwrap.dedent(ast.get_source_segment(nested, fn))
                        if 'stations_removed_after_discovery' in text and 'spatial_ready' in text:
                            candidates.append(text)
    assert len(set(candidates)) == 1
    original = candidates[0]
    assert original.count('count_certificate=len(self.cleared)>=16') == 1
    changed = original.replace('count_certificate=len(self.cleared)>=16', 'count_certificate=False  # experimental pure-geometry certificate')
    return original, changed


def main():
    registration = initial_registration()
    assert not (HERE/'registration.json').exists(), 'Never overwrite an existing registration'
    (HERE/'snapshots').mkdir(exist_ok=True)
    source = PARENT.read_text()
    (HERE/'snapshots/b3_parent.py').write_text(source)
    assert sha(HERE/'snapshots/b3_parent.py') == PARENT_SHA
    original_run, pure_run = pure_run_source(source)
    (HERE/'snapshots/original_directional_run.txt').write_text(original_run+'\n')
    (HERE/'snapshots/pure_directional_run.txt').write_text(pure_run+'\n')
    parent = load_module(PARENT, 'coverage_parent_inspection')
    baseline = parent.Solver(NoActions(), mode=4)
    assert baseline.points == points21()
    builds = []
    for name, layout, rotation, pure in [('fixed21', 21, False, False), ('fixed22', 22, False, False),
                                         ('rotating21', 21, True, False), ('pure21', 21, False, True),
                                         ('pure22', 22, False, True)]:
        pts = points21() if layout == 21 else points22()
        wrapper = f'''\n# Coverage experiment only: identical embedded B3 parent above.
import types as _coverage_types
_B3 = Solver
_COVERAGE_LAYOUT = {layout}
_COVERAGE_ROTATION = {rotation!r}
_COVERAGE_PURE = {pure!r}
_COVERAGE_POINTS = {pts!r}
_COVERAGE_CANONICAL21 = {points21()!r}
_coverage_base = next(c for c in _Directional.__mro__ if c.__name__ == '_di_Solver')
_coverage_ns = dict(_coverage_base.run.__globals__)
exec(compile({pure_run!r}, __file__ + ':pure_geometry_run', 'exec'), _coverage_ns)
_coverage_pure_run = _coverage_ns['run']

class _CoverageDirectional(_Directional):
    def __init__(self, env, mode=4, **config):
        config['a2_rotation'] = _COVERAGE_ROTATION
        if _COVERAGE_PURE:
            config['upper_bound_stop'] = False
            config['stop_discovered'] = False
        super().__init__(env, mode=mode, **config)
        if self.points != _COVERAGE_CANONICAL21:
            raise ValueError('Parent discovery points differ from pinned 21-point certificate')
        # No scans or positive observations exist before this certified layout replacement.
        if any(self.scanned.values()) or any(self.observations.values()):
            raise ValueError('Layout replacement after observation would invalidate station identities')
        self.points = list(_COVERAGE_POINTS)

    def all_sources_discovered(self):
        if _COVERAGE_PURE:
            return False
        return len(self.cleared | {{c for c in range(1,21) if self.observations[c]}}) >= 16

    def run(self):
        result = _coverage_pure_run(self) if _COVERAGE_PURE else super().run()
        result['coverage_experiment'] = dict(layout=_COVERAGE_LAYOUT, rotation=_COVERAGE_ROTATION, pure_geometry=_COVERAGE_PURE)
        return result

class Solver:
    def __new__(cls, env, mode=3, **config):
        merged = {{**OPTIMIZED_CONFIGS[mode], **config}}
        return _CoverageDirectional(env, mode=mode, **merged) if mode == 4 else _B3(env, mode=mode, **merged)
'''
        path = HERE/'snapshots'/f'{name}.py'
        path.write_text(source+wrapper)
        mod = load_module(path, 'coverage_build_'+name)
        state = mod.Solver(NoActions(), mode=4)
        assert state.points == pts and state.trace == []
        assert state.config['a2_rotation'] == rotation
        if pure:
            assert not state.config['upper_bound_stop'] and not state.config['stop_discovered']
            assert state.all_sources_discovered() is False
        for method in ('second_point', 'clear', 'measure', '_e2_service_round', 'optical_points', 'cover_polygon'):
            left, right = getattr(type(state), method), getattr(type(baseline), method)
            assert left.__code__.co_code == right.__code__.co_code, method
        builds.append(dict(name=name, path=str(path.relative_to(HERE)), sha256=sha(path),
                           points=pts, rotation=rotation, pure_geometry=pure,
                           local_method_bytecode_matches_parent=True, construction_environment_actions=0))
    registration['builds'] = builds
    registration['pure_run_change'] = 'Only final count_certificate assigned False; both count-based early branches disabled through fixed config.'
    registration['build_script_sha256'] = sha(__file__)
    registration['common_script_sha256'] = sha(HERE/'common.py')
    dump(HERE/'registration.json', registration)
    print(json.dumps(dict(status='built', candidates=len(builds), parent_sha256=PARENT_SHA), ensure_ascii=False))


if __name__ == '__main__':
    main()
