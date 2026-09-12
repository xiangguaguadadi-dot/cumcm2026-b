# Joint station geometry v1

Pure public-state API: `propose(snapshot, options=None) -> list[Plan]`,
`verify(snapshot, plan, deadline=None, keep_leaves=False) -> dict`.
The snapshot matches the planner v1 adapter; historic evidence is reconstructed
from actual accepted measure responses in `history`, never `scanned` indexes.
`negative_points` is redundant public context and is not trusted as a substitute.

Each Plan retains all pending station IDs, changes 2–4 mutable coordinates, and
assigns the explicit paid channels. An empty channel list retires the station
only after every unknown channel is continuously covered by actual past
no_signal locations plus all retained planned points. Failed clear disks are
currently conservatively ignored. Past observations and source-service polygons
are never moved. The planner must execute every retained channel action unless
that channel has actually been discovered; it must reverify before committing.

Options: `block_sizes=[2]` (or `[3]`, `[4]`), `max_plans=6`,
`max_seconds=.25` Q3 / `1.5` Q4, `minimum_proxy_gain_s=0`,
`prune_channels=True`. The first candidate family jointly attracts blocks of
stations toward public source-service anchors (80, 200, 450 m steps); radial and
mixed-route smoothing alternatives are included. This is a finite search, not a
global optimum. A two-opt full public-task route plus paid unknown measure and
switch fees is a selection proxy. Localization outcomes, station retests and
conditional detection costs remain unmodeled. Proxy savings are not real solver
performance.

Continuous certification uses exact Python integer inequalities on a dyadic
partition of [-2048,2048]^2. The disk domain is excluded only with an exact
minimum-square-distance test. Every retained whole square is covered by a
single radius-safe receiver (Q3), or lies robustly in the convex hull of
receivers all radius-safe for the square (Q4). Source direction half-planes are
closed, so this hull condition guarantees at least one listening point in every
possible emitting half-plane. Actual float station coordinates are rounded by
exact rational arithmetic to 1/1024 m; <=0.5/1024 m coordinate errors are
absorbed by 2/1024 m radial and hull margins. The hull edge inequality uses an L1
edge bound and integer cross products, so no floating orientation decision is
used for certification. Unknown/timeout/degenerate cases never certify.

`keep_leaves=True` retains the proof tree. `replay_certificate` independently
checks the supplied witnesses and merges every sibling square to the root;
missing, duplicated or overlapping leaves cannot pass by area summation.
A result without retained leaves is still reproducible by re-running `verify`;
performance runs may retain hashes/statistics and reconstruct selected proofs.

Pure checks (no environment runs):

```sh
python3 -m unittest discover -s experiments/jointplan_v1/geometry/tests -v
```

As of first handoff: 12 checks pass. The original Q3 seven-point and Q4
21-point layouts certify in approximately 2 ms / 150 ms on this machine.
A synthetic radial service-anchor fixture yields certified 2-, 3- and 4-station
alternatives. Its proxy reduction is a construction check only. No complete
strategy performance claim is made before registered environment replay.
