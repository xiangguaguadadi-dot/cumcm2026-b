# Natural-boundary joint planner

`candidate_disabled.py` inserts only a read-only hook in the exact frozen
`fusion_r5` outer run loop. The coordinator has reported P0: 48 paired worlds,
9,589 business calls on each side, identical requests and final semantic state,
96 complete clears. The pure fixtures in `tests/` are additional synthetic
protocol checks, not environment performance results.

`candidate_joint.py`, `candidate_a_only.py`, and `candidate_b_only.py` expose
`OPTIMIZED_CONFIGS` and `Solver(env, mode, **config).run()`. Geometry is imported
from `experiments/jointplan_v1/geometry`; it must be frozen with these files.
Disabled adapter and parent are also dependencies. No official interface or
frozen environment file changes are made.

## P1 exact public-prefix replay

Pass the structured option:

```json
{"jointplan_replay": {"snapshot_hash": "PUBLIC_HASH", "plan": {}, "scheduler": "parent"}}
```

Replace `plan` with the complete frozen A plan. Before the exact hash occurs,
the original parent action sequence is retained. At that hash the plan is
independently verified and committed once. `scheduler=parent` is the default
for isolating geometric intervention; `scheduler=mixed` also chooses the next
natural unit using B. A hash that never occurs causes no new action and is
reported as `replay_status=not_matched`. A stale plan is rejected. The runner
must preserve these missed/rejected records instead of treating them as an
effective candidate. All execution begins with the one real `enter`.

## Normal actor options

- `jointplan_geometry` / `jointplan_mixed`: component ablation.
- `jointplan_intervention_limit=2`: maximum commits or mixed interventions.
- `jointplan_boundary_visited=[1,3]`: initial exposed-development boundary rule.
- `jointplan_geometry_options`: forwarded to A (`block_sizes`, `max_plans`,
  `max_seconds`, `prune_channels`, and the registered step-scale parameters).
- `jointplan_candidate_rank`: finite-candidate diagnostic replay only.
- `jointplan_capture_snapshots=True`: retain detached snapshots for audit.
- `jointplan_verify_seconds=2`: verifier anytime guard; unknown never certifies.

## Execution and recovery

Only future station coordinates and explicit per-station channel obligations
are committed. Parent `measure`, `localize`, finite optical plans and protected
clear behavior remain intact. A planned unknown channel is measured and paid
unless actual history has already discovered/cleared it. New points do not
inherit old coordinate evidence. Parent `scanned` indexes continue to support
its approximate route model; the final certificate instead uses A's verifier
over accepted real no-signal coordinates.

If that final verifier is unknown/failed, append every original certified
layout point as a fresh obligation and complete it from the current physical
state. All additional scans, localization, failed/near clears and movement are
paid. Deadline, current channel, prior positions, costs and history are never
rolled back, and no second `enter` is performed. Real protocol exceptions are
propagated; only preparation failures before actions fall through to the parent.

## B cost model and limitations

`mixed_planner.py` generates complete remaining task orders and prices all
future unknown-channel station measurements and switches in the all-negative
discovery branch. Known source service estimates include trial success,
failure-plus-measure continuation, certified stand-off when applicable, and
multiple public polygon endpoint samples. The first hypothetical action is
shared across those samples. This differs from a single weighted-distance
score: station/source insertion is selected using the full modeled route.

This model is approximate. It does not reproduce the entire frozen policy
inside hypothetical environments, and extra discoveries invalidate its
forecast. Unknown new-source service costs, exact directional loss recovery,
finite optical portfolio selection and branch-specific future channel states
are not exactly predicted. Every decision records predicted remaining seconds
and the actual entire paid suffix for audit. The estimate is neither a lower
bound nor a performance result. This initial model must be judged by registered
real full replay; no deeper observation tree or training is started here.

The 96 coordinator public prefixes took 1.19 seconds total / 0.057 seconds max
for pure first-version B route modeling on Python 3.12. These timings exclude
geometry generation and are not environment runs. Raw model diagnostics are
in `research/mixed_proxy_public_prefix_v1.json`.

Run pure tests with `/opt/homebrew/bin/python3.12 -S -m unittest discover -s
experiments/jointplan_v1/planner/tests -v`. Python 3.9 cannot run the frozen
parent's `int.bit_count`; `-S` avoids unrelated local site initialization.

## Standalone packaging

`build_standalone.py --repo ROOT --out NEW_FILE.py --entry joint` produces one
standard-library file and a `.manifest.json` sidecar. Entry choices also include
`a-only`, `b-only`, `disabled` and `parent`. `--config-json` may supply per-mode
normal actor settings; replay-prefix data and callbacks are rejected as default
configuration. Existing output paths are never overwritten.

The builder records raw and transformed source hashes, replaces only filesystem
component loaders with in-memory modules, and explicitly binds the frozen
parent's optional neighboring-JSON fallback to its same built-in certified
points. It discovers relative geometry module dependencies for later versions.
No sibling source, data file or outer `__file__` value is required at runtime.
The packaging fixtures disable filesystem access and omit `__file__`, then run
pure near/silent protocol fixtures and continuous Q3 certification successfully.
The disabled bundle retains the exact synthetic parent action sequence.

`research/packaging_v1/joint_standalone_preview.py` is a source-bounded packaging
preview (634,213 bytes; SHA256
`834d06f89164765592fc476b1e5a3213ef43e07aa81d30468d376dbbd9c7d5be`), not a new
environment-validated candidate. Its sidecar binds the coordinator sources used
at build time. All 12 current pure tests pass; the preview has zero environment
runs. Rebuild and revalidate the final artifact after component selection.
