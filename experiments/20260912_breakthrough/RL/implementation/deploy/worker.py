"""Separate JSON-only public candidate worker. Never imports evaluator/local_env."""
from __future__ import annotations
import json
import sys
from .operations import generate


def main():
    for line in sys.stdin:
        request_id=None
        try:
            request = json.loads(line)
            if set(request)!={'request_id','payload'}:
                raise ValueError('Unknown public-worker envelope fields')
            request_id=request['request_id']
            response = dict(ok=True, choice=generate(request['payload']))
        except Exception as exc:
            response = dict(ok=False, error=type(exc).__name__ + ': ' + str(exc))
        response['request_id']=request_id
        print(json.dumps(response, ensure_ascii=False, allow_nan=False, separators=(',',':')), flush=True)


if __name__ == '__main__':
    main()
