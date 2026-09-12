"""Extract constant embedded modules for review; never execute inspected code."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path


def inspect(source, out):
    out.mkdir(parents=True, exist_ok=False)
    seen, modules = set(), []

    def visit(text, origin):
        digest = hashlib.sha256(text.encode()).hexdigest()
        if digest in seen:
            return
        seen.add(digest)
        tree = ast.parse(text)
        name = f'module_{len(modules):02d}_{digest[:12]}.py'
        (out/name).write_text(text)
        record = dict(file=name, origin=origin, sha256=digest, bytes=len(text.encode()), imports=[], review_calls=[])
        modules.append(record)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import,ast.ImportFrom)):
                record['imports'].append({'line':node.lineno,'code':ast.unparse(node)})
            if isinstance(node, ast.Call):
                func = ast.unparse(node.func)
                if func in ('open','eval','exec','__import__','getattr','setattr','vars','globals','locals') or any(
                    word in func.lower() for word in ('read_text','read_bytes','pickle','load','getattr','__dict__')):
                    record['review_calls'].append({'line':node.lineno,'function':func})
                if isinstance(node.func,ast.Name) and node.func.id == 'compile' and node.args:
                    value=node.args[0]
                    if isinstance(value,ast.Constant) and isinstance(value.value,str):
                        visit(value.value, f'{name}:{node.lineno}')
    visit(source.read_text(),str(source))
    result = dict(source=str(source.resolve()),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  note='Review aid only; AST pattern checks do not prove information isolation.',modules=modules)
    (out/'index.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return {'modules':len(modules),'imports':sorted({r['code'] for m in modules for r in m['imports']}),
            'review_calls':sum(len(m['review_calls']) for m in modules)}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(inspect(args.source,args.out),ensure_ascii=False))
