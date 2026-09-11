# E2 stage-four plan

Current parent is frozen S1 (Q3 R2 R4 / Q4 R3 R5). Only experiments/E2_refine is writable for this research. Initial Q3 behavior remains S1.

## Reading and observation

Read AGENTS, README, evaluation standard, stage3 report, compact 70-node index and stage3 progress. Then read only the current Q3 task-cost gate, current Q4 sharing/localization/recovery/station-scan code and relevant node summaries (R2 R3, R3 R1, A3 R3, A4 R7, Q4_COST_GATE_PROPOSED). This is source/component reading and aggregate raw-row analysis; not an assertion of reviewing every historical trajectory.

Raw S1 rows give Q4 340.531263 movement and 133.366230 nonmovement seconds/source, versus Q3 174.736750 / 61.140196. Q4 opportunity sensing ranks radius shrinkage while deferred station scans retest all pending sources in a broad range bound, including already clearable regions. These may pay for geometry that does not avoid a future dedicated action. Dedicated single-target recovery remains another possible travel bottleneck.

## First hypotheses and contrasts

R1: Replace Q4 supplementary-measure radius gain with an expected downstream action-cost reduction. Predicted positive branches use one center hypothesis and three hypothetical errors; no-signal leaves the entire authoritative region unchanged, weighted by the existing orientation/range visibility approximation. Compare (a) current S1, (b) no opportunity sensing, (c) cost gate only at opportunity arrivals, (d) same cost gate also at deferred station revisits. Unknown-channel discovery scanning and exit certificates remain unchanged.

Expected savings: remove low-value <=6 s supplementary reads and improve the subset that actually avoids dedicated approach/recovery moves; all movement and clear outcomes remain paid for through interfaces. This is a planning proxy, not a probabilistic guarantee or the published DRD algorithm.

Initial new development: 96 mixed-source Q4 cases, 8 per existing physical/noise scenario family, unique seeds 45000000..45000095. Save complete cases, all attempts and selected raw traces. Use rules and quick to catch changes, then a useful candidate receives full and 4800 exposed comparisons to fixed S1 and previous best. Do not run a new final holdout.

E1 independently studies conditional discovery routes and joint continuous clearing stops. E3 studies new multi-step bearing/localization mechanisms. E2 avoids duplicating those first lines; if R1 saturates, use its raw decision/action failures to choose a distinct structural next experiment, rather than stop after a fixed round count.

## R2 pre-experiment entry

R1's 12 saved S1 traces show about 17450 seconds of target-service movement versus 724 seconds of opportunistic sensing. After committing the station-gate result, test two isolated changes on frozen r1_station_only: (a) immediately clear every known source whose entire retained polygon lies within 20 meters of the actual current stop, (b) replace an indivisible whole-source localize call with one original service-loop round, then return to global route selection. In (b) a per-channel counter persists; at most the original 9 rounds occur before the same finite optical fallback, so repeated selection cannot reset the escape budget. Neither changes second-point candidates, source truth access, discovery scanning, or final certificates. R2 development uses 96 further mixed Q4 cases, seeds 45000096..45000191; S1 and own R1 are explicit actual controls. Do not mix both changes before observing their isolated effects.

## R3 pre-experiment entry

With R2 frozen, use the actual failed optical clear as a <=20m exclusion independent of source antenna direction. Contrast (a) convex outer hull of the polygon outside retained failure disks, repeated after later direction measurements, and (b) discard an optical grid cell only when its entire clipped feasible polygon is contained in one known failed disk. Cell-center membership alone is insufficient and is never used. The convex hull may fill the excluded hole back in; the cell variant retains disk history separately so this distinction is testable. Do not use radio no_signal as a1000m exclusion for Q4. New96 mixedQ4 development cases/seeds45000192..45000287, controls fixedS1 and frozenR2. Keep original optical covering and count/discovery exits. Mathematical safety: a failed optical attempt implies true source outside its20m disk; a convex disk containing every clipped-cell vertex contains the entire cell intersection. Use20-1e-6 margin. Preserve finite fallback and refuse contradictory empty geometry.

## R4 pre-experiment entry

On12 saved R2 development trajectories, finite optical fallback accounted for15blocks/49clear actions/375.476 virtual seconds; the longest block had14actions and114.017seconds. Test one and three paid optical actions per block, with an immutable finite complete-grid queue per channel, returning to global task selection. Completed failed attempts alone consume queue items; no geometric region is discarded from point-center membership. The next actual grid point replaces that source's centroid in the existing route proxy while its queue is active. Any later sensing only shrinks the true feasible set, so the original queued cover remains sufficient. At the existing180000second reserve switch, consume the full remaining queue, retaining the finite fallback guarantee. Source-service iteration budgets and original coverage/count exit remain. Parent is frozen R2; new96 mixedQ4 development seeds45000288..45000383, S1 andR2 actual controls. Two block sizes are a bounded structural contrast; do not expand a parameter sweep after weak/negative evidence.
