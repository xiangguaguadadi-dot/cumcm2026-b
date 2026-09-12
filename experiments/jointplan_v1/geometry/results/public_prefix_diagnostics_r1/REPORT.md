# Frozen public-prefix generation diagnostics, round 1

Input: 96 detached public snapshots supplied by the coordinator after P0.
These are the preselected two prefixes in each of 48 development worlds.
The generator consumed no hidden state, case IDs, seeds, future outcomes or
scores. There were **zero environment executions and zero business calls**.

| Question | Prefixes | Prefixes with a plan | Frozen plans | 2 / 3 / 4 station plans |
| --- | ---: | ---: | ---: | --- |
| Q3 | 48 | 6 | 36 | 12 / 12 / 12 |
| Q4 | 48 | 48 | 288 | 96 / 96 / 96 |

Each prefix has at most six plans, obtained from the fixed two-plan allowance
for each block size. Every emitted plan independently passed `verify` again.
No candidate paid-channel deletion was certified in this batch. Most unknown
channels have identical past scan histories here, so the channel assignment
optimization had no proven opportunity in these particular prefixes.

Generation took 84.754 s total. Mean / maximum generation time per block-size
variant was 0.01184 / 0.04232 s for Q3, and 0.55810 / 1.50314 s for Q4. Across
candidate checks, Q3 yielded 36 certified, 230 robust counterexamples, and 1935
unknown results; Q4 yielded 288 certified, 101 robust counterexamples, and 1238
unknown. Unknown results are never accepted. They do not prove the layouts
impossible, nor do they prove that the global strategy has no improvement.

Among the emitted plans, the mean / maximum fixed-order coordinate proxy
reduction was 72.613 / 116.417 s per whole remaining task proxy for Q3 and
1.720 / 6.255 s for Q4. These values are **not realized complete-run savings**,
not seconds/source, and not a claim toward the 200/400 target. The separate
old-geometry route-order proxy component remains in each Plan for attribution.
All source anchors are approximate public localization regions.

Q3 coverage limits the simple attraction grammar: most early known-source
anchors lie inward of the 1124 m ring, so jointly attracting future points
inward violates the tight outer coverage requirement. The certified cases
include inward contraction of the larger adaptive ring. This geometric reading
is based on public coordinates; it is not an explanation of future full-run
outcomes. A new radial compensation grammar belongs to a later version, and
must not change this frozen set.

`SPEC.json` fixes generator/source/input hashes and options. `prefixes.jsonl`
preserves per-prefix, per-size diagnostics, including every zero-candidate
prefix. `FROZEN_P1_CANDIDATES.json` is the coordinator replay input, keyed only
by public snapshot hash. Source version is geometry commit `48bbbba`, following
`3e187f6`; the accompanying diagnostic driver was not used to alter the solver.
