"""Mechanically extract embedded C7 source literals for read-only inspection."""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / 'experiments/20260911_stage4/combination/geometry_fusions/C7_both.py'
out = HERE / 'inspection'
out.mkdir(exist_ok=True)
records = []

def visit(source, name):
    tree = ast.parse(source)
    path = out / f'{name}.py'
    # Generated inspection artifact, not a candidate or shared-file edit.
    path.write_text(source)
    records.append(dict(path=str(path.relative_to(HERE)), sha256=hashlib.sha256(source.encode()).hexdigest()))
    number = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'compile' and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            visit(node.args[0].value, name + '_' + str(number))
            number += 1

visit(SOURCE.read_text(), 'C7')
(out / 'manifest.json').write_text(json.dumps(records, indent=2))
print(json.dumps(records, indent=2))
