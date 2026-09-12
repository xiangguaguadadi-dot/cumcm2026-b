"""Build a standard-library-only, source-bounded standalone candidate.

Build time reads explicitly selected source files. Generated runtime code
contains all selected sources and never resolves/reads neighboring data files.
Environment execution and candidate evaluation are deliberately absent here.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path


PARENT_SHA256 = "0bda4f711b9e9716739af8aedf456cb1eeefb47d8ba3ed230ca682c8450a96ea"


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _target(node):
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None


def _adapter_source(source):
    tree = ast.parse(source)
    changed = set()
    body = []
    for node in tree.body:
        name = _target(node)
        if name in {"_ROOT", "_PARENT_PATH", "_spec"}:
            changed.add(name)
            continue
        if name == "_SOURCE":
            node.value = ast.Name(id="_JP_PARENT_SOURCE", ctx=ast.Load())
            changed.add(name)
        elif name == "_PARENT":
            node.value = ast.parse('_JP_LOAD("parent")', mode="eval").body
            changed.add(name)
        elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "exec_module"):
            changed.add("exec_module")
            continue
        body.append(node)
    if changed != {"_ROOT", "_PARENT_PATH", "_spec", "_SOURCE", "_PARENT", "exec_module"}:
        raise ValueError("Adapter loader changed; update and review standalone transformation")
    tree.body = body
    return ast.unparse(ast.fix_missing_locations(tree)) + "\n"


def _joint_source(source):
    class LoaderTransform(ast.NodeTransformer):
        def __init__(self):
            self.changed = set()

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == "_load":
                mapping = {"jointplan_disabled_adapter": "adapter", "jointplan_mixed_planner": "mixed",
                           "jointplan_geometry": "geometry"}
                if not node.args or not isinstance(node.args[0], ast.Constant) or node.args[0].value not in mapping:
                    raise ValueError("Unrecognized joint component loader")
                name = mapping[node.args[0].value]
                self.changed.add(name)
                return ast.Call(func=ast.Name(id="_JP_LOAD", ctx=ast.Load()),
                                args=[ast.Constant(value=name)], keywords=[])
            return self.generic_visit(node)

    tree = ast.parse(source)
    tree.body = [node for node in tree.body if not (
        _target(node) == "_DIR" or isinstance(node, ast.FunctionDef) and node.name == "_load")]
    transformer = LoaderTransform()
    tree = transformer.visit(tree)
    if transformer.changed != {"adapter", "mixed", "geometry"}:
        raise ValueError("Joint loader changed; update and review standalone transformation")
    return ast.unparse(ast.fix_missing_locations(tree)) + "\n"


_RUNTIME = '''
import hashlib as _jp_hashlib
import sys as _jp_sys
import types as _jp_types

_JP_MODULES = {}
_JP_NAMESPACE = "_jointplan_bundle_" + BUNDLE_MANIFEST["source_set_sha256"][:16]

def _jp_remove_optional_data_dependency(parent):
    # The frozen implementation normally falls back to these exact built-in
    # certified layouts when its optional neighboring JSON is absent. Binding
    # that branch explicitly makes the standalone independent of all paths.
    seen = set()
    stack = [parent]
    while stack:
        module = stack.pop()
        if id(module) in seen:
            continue
        seen.add(id(module))
        values = module.__dict__
        for prefix in ("_sp", "_di"):
            default_name, certified_name = prefix + "_default_points", prefix + "_certified_points"
            if default_name in values and certified_name in values:
                def built_in_points(mode, _values=values, _name=certified_name):
                    return _values[_name](mode)
                values[default_name] = built_in_points
        for child in list(values.values()):
            if isinstance(child, _jp_types.ModuleType) and getattr(child, "__file__", None) == "<embedded-frozen-parent>":
                stack.append(child)

def _JP_LOAD(name):
    if name in _JP_MODULES:
        return _JP_MODULES[name]
    if name == "geometry":
        module_name = _JP_NAMESPACE + ".geometry"
        module = _jp_types.ModuleType(module_name)
        module.__package__ = module_name
        module.__path__ = []
        module.__file__ = "<embedded-geometry>"
        _JP_MODULES[name] = module
        _jp_sys.modules[module_name] = module
        for part in BUNDLE_MANIFEST["geometry_load_order"]:
            child_name = module_name + "." + part
            child = _jp_types.ModuleType(child_name)
            child.__package__ = module_name
            child.__file__ = "<embedded-geometry-" + part + ">"
            _jp_sys.modules[child_name] = child
            setattr(module, part, child)
            exec(compile(_JP_SOURCES["geometry." + part], child.__file__, "exec"), child.__dict__)
        exec(compile(_JP_SOURCES["geometry"], module.__file__, "exec"), module.__dict__)
        return module
    module = _jp_types.ModuleType(_JP_NAMESPACE + "." + name)
    module.__file__ = "<embedded-frozen-parent>" if name == "parent" else "<embedded-" + name + ">"
    module.__dict__.update(_JP_LOAD=_JP_LOAD, _JP_PARENT_SOURCE=_JP_SOURCES["parent"])
    _JP_MODULES[name] = module
    exec(compile(_JP_SOURCES[name], module.__file__, "exec"), module.__dict__)
    if name == "parent":
        _jp_remove_optional_data_dependency(module)
    return module

for _jp_name, _jp_source in _JP_SOURCES.items():
    if _jp_hashlib.sha256(_jp_source.encode("utf-8")).hexdigest() != BUNDLE_MANIFEST["embedded_sha256"][_jp_name]:
        raise RuntimeError("Embedded component checksum mismatch: " + _jp_name)

_JP_ENTRY = _JP_LOAD("parent" if _JP_ENTRY_KIND == "parent" else "adapter" if _JP_ENTRY_KIND == "disabled" else "joint")
OPTIMIZED_CONFIGS = {m: dict(c) for m, c in _JP_ENTRY.OPTIMIZED_CONFIGS.items()}
if _JP_ENTRY_KIND == "a-only":
    for _jp_config in OPTIMIZED_CONFIGS.values():
        _jp_config.update(jointplan_geometry=True, jointplan_mixed=False)
elif _JP_ENTRY_KIND == "b-only":
    for _jp_config in OPTIMIZED_CONFIGS.values():
        _jp_config.update(jointplan_geometry=False, jointplan_mixed=True)
for _jp_mode, _jp_config in _JP_STATIC_CONFIG.items():
    OPTIMIZED_CONFIGS[int(_jp_mode)].update(_jp_config)
BASELINE_CONFIG = dict(_JP_ENTRY.BASELINE_CONFIG)

class Solver:
    def __new__(cls, env, mode=3, **config):
        return _JP_ENTRY.Solver(env, mode=mode, **{**OPTIMIZED_CONFIGS[mode], **config})
'''


def build_sources(repo, entry="joint", config=None, geometry_dir=None):
    repo = Path(repo).resolve()
    planner = repo / "experiments/jointplan_v1/planner"
    geometry = Path(geometry_dir).resolve() if geometry_dir else repo / "experiments/jointplan_v1/geometry"
    paths = {"parent": repo / "experiments/parallel_v2_coordinator/fusion_r5.py",
             "adapter": planner / "candidate_disabled.py", "mixed": planner / "mixed_planner.py",
             "joint": planner / "candidate_joint.py", "geometry": geometry / "__init__.py"}
    geometry_order, visiting, complete = [], set(), set()
    def discover_geometry(name):
        if name in complete:
            return
        if name in visiting:
            raise ValueError("Cyclic geometry imports need explicit bundle review")
        visiting.add(name)
        path = geometry / ("__init__.py" if not name else name + ".py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                if node.level != 1 or not node.module or "." in node.module:
                    raise ValueError("Nested geometry import needs explicit bundle review")
                discover_geometry(node.module)
        if name:
            paths["geometry." + name] = path
            geometry_order.append(name)
        visiting.remove(name)
        complete.add(name)
    discover_geometry("")
    raw = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    if sha256(raw["parent"]) != PARENT_SHA256:
        raise ValueError("Parent must match the approved frozen fusion_r5 SHA256")
    if entry not in {"joint", "a-only", "b-only", "disabled", "parent"}:
        raise ValueError("Unknown standalone entry")
    config = config or {}
    for mode, values in config.items():
        if str(mode) not in {"3", "4"} or not isinstance(values, dict):
            raise ValueError("Static configuration must be per mode 3/4")
        if any(k in values for k in {"jointplan_replay", "jointplan_prefix_hash", "jointplan_geometry_provider",
                                     "jointplan_snapshot_callback", "jointplan_candidate_rank"}):
            raise ValueError("Evaluation-prefix data/callables cannot be embedded as a normal actor default")
    json.dumps(config, allow_nan=False)
    embedded = dict(raw, adapter=_adapter_source(raw["adapter"]), joint=_joint_source(raw["joint"]))
    source_hashes = {name: sha256(source) for name, source in raw.items()}
    manifest = {"schema_version": 1, "kind": "standalone_standard_library_candidate", "entry": entry,
                "raw_source_sha256": source_hashes,
                "embedded_sha256": {name: sha256(source) for name, source in embedded.items()},
                "source_set_sha256": sha256(json.dumps(source_hashes, sort_keys=True, separators=(",", ":"))),
                "static_config": config,
                "geometry_load_order": geometry_order,
                "transformations": ["replace filesystem component loaders with in-memory source modules",
                    "bind frozen optional-JSON default-point fallback to the same built-in certified layouts"],
                "environment_runs": 0}
    code = '"""Standalone jointplan candidate; component hashes in BUNDLE_MANIFEST."""\n'
    code += "BUNDLE_MANIFEST = " + repr(manifest) + "\n"
    code += "_JP_ENTRY_KIND = " + repr(entry) + "\n"
    code += "_JP_STATIC_CONFIG = " + repr(config) + "\n"
    code += "_JP_SOURCES = " + repr(embedded) + "\n"
    code += _RUNTIME
    compile(code, "<generated-standalone-check>", "exec")
    manifest = dict(manifest, standalone_sha256=sha256(code), standalone_bytes=len(code.encode("utf-8")))
    return code, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--geometry-dir", type=Path)
    parser.add_argument("--entry", choices=["joint", "a-only", "b-only", "disabled", "parent"], default="joint")
    parser.add_argument("--config-json", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config_json.read_text(encoding="utf-8")) if args.config_json else None
    if args.out.exists() or args.out.with_suffix(".manifest.json").exists():
        raise SystemExit("Refusing to overwrite an existing frozen bundle or manifest")
    code, manifest = build_sources(args.repo, entry=args.entry, config=config, geometry_dir=args.geometry_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(code, encoding="utf-8")
    args.out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "sha256": manifest["standalone_sha256"],
                      "bytes": manifest["standalone_bytes"], "environment_runs": 0}))


if __name__ == "__main__":
    main()
