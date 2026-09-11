# E2 refinement report — R1 accepted, research continues

Current standalone snapshot: `experiments/E2_refine/snapshots/r1_station_only.py`. SHA256 `c459591b21c192fce79d6d93a9d753f21c0ef09ba8b46d8821803d1f929d904c`. It embeds both frozen S1 components, so no deployment dependency is needed.

## Change

Q4 retains S1 opportunity sensing and route selection. At an actual coverage station it still measures every undiscovered channel and records the same discovery evidence, but retests an already discovered source only when a finite downstream action-cost proxy predicts that the positive-observation benefit exceeds the 5–6 second measurement fee. Visibility uses the existing orientation/range hypothesis model. `no_signal` does not remove any possible location: its continuation cost retains the entire current polygon. Known unresolved sources remain pending for actual localization/clear; every exit still uses the original complete geometric coverage or 16-distinct-source certificate.

## Actual result

Both 4800-case candidates were actually executed on full v1 plus previous_final. Reuse covers only the exact-hash already executed v1 half. Current result: Q3 235.876945811892, Q4 466.842681464825 seconds/source. Every one of 4800 cases completed; each problem cleared 30970/30970 sources. Q3 is identical to S1 on all 2400 rows. Q4 improves 7.054811534819 seconds/source (1.488679%), with 2044 faster, 276 equal and 80 slower cases. It also improves 0.562502812091 seconds/source over cost_all on the same cases.

The largest Q4 regression is 55.849658375 seconds/source (LOCAL-v1-q4-exactly16_sources-5018); every positive regression is retained in results/r1_station_only_regressions.json. Per-suite and per-scenario means and all raw rows are in results/r1_station_only_exposed/. This is exposed local research regression, not official testing or a fresh holdout.

## Controls and interpretation

96 new legal mixed-source Q4 cases (unique seeds 45000000..45000095) give S1 465.136981317, off 481.828134225, opportunity cost 466.108429079, cost_all 458.633598800, station_only 458.007845173 and clearable-only skip 463.294170319 seconds/source. All complete. The station-only winner is 87 faster / 9 equal / 0 slower in development; its movement increases 0.280763986 seconds/source and its nonmovement decreases 7.409900130. Thus the established R1 mechanism is useful selective station retesting, predominantly reducing paid reads, not proven avoidance of dedicated travel. The simpler radius<=20 skip explains only part of the gain.

Read-only diagnosis inspected 12 saved raw S1 and 12 corresponding cost_all trajectories, not the entire historical corpus: known-source station measures fell from 281 to 88 in these traces, while undiscovered-channel observations remained 2826 in both. Raw trace paths and counts are recorded in results/r1_trace_diagnosis.json.

Rules: 12 frozen rule tests passed for each code build; every candidate change ran quick120, no missing/error rows. Five quick runs, two full runs, two 2400 previous_final completions and 576 development executions total **10776 actual strategy executions**, with **96 distinct new development cases**. Cache reuse is not counted as execution.

## Next hypotheses

The R1 result does not exhaust Q4 travel. Next, test independently (1) clearing other already certified sources at the current real stopping point and (2) a bounded single-target service round that returns to global scheduling with persistent progress. The latter changes a planning unit, not the measurement point candidate set; E1 is researching conditional discovery routes and joint clear-region points, E3 cross-target/multi-step bearing selection. Failure-clear exclusion is another available component; do not mix it into the same ablation without evidence.
