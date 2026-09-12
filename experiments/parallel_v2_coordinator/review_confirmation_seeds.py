"""Compare reserved seeds with recorded inherited and current research seeds."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMPAIGN = ROOT.parent


def collect(value, context=False):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from collect(item, context or 'seed' in key.lower())
    elif isinstance(value, list):
        for item in value:
            yield from collect(item, context)
    elif context and type(value) is int:
        yield value


def main():
    out = HERE / 'confirmation_seed_review.json'
    assert not out.exists()
    reserved = set(json.loads((HERE / 'confirmation_cases/manifest.json').read_text())['seeds'])
    roots = [ROOT / 'evaluation', ROOT / 'experiments']
    roots += [CAMPAIGN / agent / 'experiments' / ('parallel_v2_' + agent) for agent in ('a1', 'a2', 'a3')]
    known, sources = set(), []
    scanned = 0
    for root in roots:
        for path in sorted(root.rglob('*.json')):
            if HERE in path.parents and 'confirmation' in str(path.relative_to(HERE)):
                continue
            raw = path.read_bytes()
            if b'seed' not in raw.lower():
                continue
            data = json.loads(raw)
            seeds = set(collect(data))
            scanned += 1
            if seeds:
                known.update(seeds)
                sources.append({'path': str(path.relative_to(CAMPAIGN)),
                    'sha256': hashlib.sha256(raw).hexdigest(), 'seed_values': len(seeds)})
    result = dict(confirmation_seeds=sorted(reserved), known_seed_values=len(known),
        overlap=sorted(known & reserved), scanned_seed_bearing_json=scanned, sources=sources,
        scope='Inherited coordinator experiment/evaluation JSON and all three current agent experiment JSON; scalar integers below seed-named keys.',
        limits='Recorded local seeds only; does not certify any official random stream or unrecorded external execution.')
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    assert not result['overlap'], result['overlap']
    print(json.dumps({k:v for k,v in result.items() if k not in ('sources','confirmation_seeds')},ensure_ascii=False))


if __name__ == '__main__':
    main()
