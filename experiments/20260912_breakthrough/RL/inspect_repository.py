"""AST-only nested-source reading aid. No solver instance or environment runs."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
C7 = ROOT.parents[2] / "20260911_stage4/combination/geometry_fusions/C7_both.py"
# ROOT is .../experiments/20260912_breakthrough/RL.
C7 = ROOT.parent.parent / "20260911_stage4/combination/geometry_fusions/C7_both.py"
TARGETS = {"measure", "clear", "_accept", "_after_measure", "__init__", "run", "second_point", "share_observations"}

def walk_source(text, label, found):
    try: tree = ast.parse(text)
    except SyntaxError: return
    lines = text.splitlines()
    for obj in tree.body:
        if isinstance(obj, ast.ClassDef):
            for method in obj.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name in TARGETS:
                    found.append({"label": label, "class": obj.name, "method": method.name,
                                  "first_line": method.lineno,
                                  "source": "\n".join(lines[method.lineno-1:method.end_lineno])})
    for obj in ast.walk(tree):
        if isinstance(obj, ast.Call) and isinstance(obj.func, ast.Name) and obj.func.id == "compile":
            if obj.args and isinstance(obj.args[0], ast.Constant) and isinstance(obj.args[0].value, str):
                child_label = (ast.literal_eval(obj.args[1]) if len(obj.args)>1 and isinstance(obj.args[1], ast.Constant) else f"{label}:embedded")
                walk_source(obj.args[0].value, child_label, found)

found=[]
raw=C7.read_text()
walk_source(raw, "C7_both.py", found)
(ROOT / "source_methods.json").write_text(json.dumps({"source": str(C7), "sha256": hashlib.sha256(raw.encode()).hexdigest(), "methods": found}, ensure_ascii=False, indent=2))
for row in found:
    if row["method"] in {"measure","clear","_accept","share_observations"}:
        print(f"\n=== {row['label']} {row['class']}.{row['method']}:{row['first_line']} ===\n{row['source']}")
