"""Create a self-contained S0-derived candidate; build-time parent reads only."""
from pathlib import Path
import ast, hashlib, json, io, tokenize

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'experiments/R2_open'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rename(s, mapping):
    toks = []
    for tok in tokenize.generate_tokens(io.StringIO(s).readline):
        if tok.type == tokenize.NAME and tok.string in mapping:
            tok = tok._replace(string=mapping[tok.string])
        toks.append(tok)
    return tokenize.untokenize(toks)


def defs(s):
    return {x.name: x for x in ast.parse(s).body if isinstance(x, (ast.FunctionDef, ast.ClassDef))}


def main():
    b1 = ROOT / 'experiments/20260911_stage3/baseline/B1_R1.py'
    b3 = ROOT / 'experiments/20260911_stage3/baseline/B3_R1.py'
    a2 = ROOT / 'experiments/20260911_agent_campaign/final_candidates/A2_information_R8.py'
    s = b1.read_text()
    b3s = b3.read_text()
    b3names = {x: '_di_' + x[3:] for x in defs(b3s) if x.startswith('q4_')}
    b3names.update({x.id: '_di_' + x.id[3:] for n in ast.parse(b3s).body if isinstance(n, ast.Assign)
                    for t in n.targets for x in ast.walk(t) if isinstance(x, ast.Name) and x.id.startswith('q4_')})
    b3renamed = rename(b3s, b3names)
    old = ast.get_source_segment(s, defs(s)['_di_certified_points'])
    new = ast.get_source_segment(b3renamed, defs(b3renamed)['_di_certified_points'])
    s = s.replace(old, new, 1)
    checks = {}
    for name, node in defs(b3renamed).items():
        if name.startswith('_di_'):
            checks[name] = ast.dump(node, include_attributes=False) == ast.dump(defs(s)[name], include_attributes=False)
    assert checks and all(checks.values()), checks
    # Remove only B1's final public dispatch/config; keep both original engines
    # and the opportunity-sensing mixin, which Q3 still uses.
    s = s[:s.index('BASELINE_CONFIG=dict(_sp_BASELINE_CONFIG)')]
    a2s = a2.read_text()
    names = {x: '_geo_' + x for x in defs(a2s)}
    names.update(EPS='_geo_EPS')
    geom = '\n\n'.join(ast.get_source_segment(a2s, defs(a2s)[x])
                        for x in ('convex_hull', 'outside_disk_hull', 'add_bearing'))
    s += '\n\n' + rename(geom, names) + '\n\n' + (OUT / 'research/geometry_component.py').read_text()
    target = OUT / 'snapshots/r1_development.py'
    target.write_text(s)
    audit = dict(parents={str(p): sha(p) for p in (b1, b3, a2)},
                 output=str(target), sha256=sha(target),
                 q4_normalized_ast_equivalence=checks,
                 transform='B1 engines plus B3 certified_points, geometry helper extraction, explicit new Q3 subclass; no runtime source reads',
                 inherited_runtime_dependencies='Python standard library only; no sidecar coverage file')
    (OUT / 'research/r1_build_provenance.json').write_text(json.dumps(audit, indent=2))
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
