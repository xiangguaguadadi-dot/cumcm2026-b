"""Bind a frozen learned action component to a frozen geometric parent class.

This changes one class binding. Geometry, model weights and component source
remain byte-identical; closed-loop evaluation is still required after fusion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--geometric-parent',type=Path,required=True)
    p.add_argument('--geometric-class',required=True)
    p.add_argument('--learned-candidate',type=Path,required=True)
    p.add_argument('--learned-prefix',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    assert a.geometric_class.isidentifier()
    parent=a.geometric_parent.read_bytes()
    learned=a.learned_candidate.read_bytes()
    prefix=a.learned_prefix.read_bytes()
    assert learned.startswith(prefix), 'Cannot identify exact frozen learner component boundary'
    component=learned[len(prefix):]
    assert b'class ' in component and b'_A3_ORIGINAL_Q4' in component
    source=(parent+b'\n# Explicit integration binding; outer package selects the final Q3.\n'
            +f'_A3_ORIGINAL_Q4 = {a.geometric_class}\n_A3_Q3 = _C7\n'.encode()+component)
    compile(source,str(a.out),'exec')
    assert not a.out.exists()
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_bytes(source)
    provenance={'candidate_sha256':sha(source),'dependencies':{},
                'geometric_parent':str(a.geometric_parent.resolve()),'geometric_parent_sha256':sha(parent),
                'geometric_parent_class':a.geometric_class,
                'learned_candidate':str(a.learned_candidate.resolve()),'learned_candidate_sha256':sha(learned),
                'learned_prefix_sha256':sha(prefix),'unchanged_learned_component_sha256':sha(component),
                'note':'A learned component changes its inherited geometric parent; evaluation required.'}
    a.out.with_suffix('.provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(provenance,ensure_ascii=False))


if __name__=='__main__':
    main()
