#!/usr/bin/env python3
"""Reproducible public-state geometric experiments. Implementation follows registration.json."""
from pathlib import Path
import argparse
import json
import sys

HERE = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, help='New output directory; existing output is never overwritten.')
    parser.add_argument('--registration-only', action='store_true')
    args = parser.parse_args()
    registration = json.loads((HERE / 'registration.json').read_text())
    if args.registration_only:
        print(json.dumps(registration, ensure_ascii=False, indent=2))
        return
    if sys.version_info < (3, 10):
        raise SystemExit('Unchanged B3 requires Python >=3.10 (int.bit_count); use python3.12 on this machine.')
    from geometry_experiment import run
    run(Path(args.out), registration)

if __name__ == '__main__':
    main()
