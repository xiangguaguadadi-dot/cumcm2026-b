# G1 integration audit (read-only, 2026-09-11)

The audit read `runners/common.py`, `g1_resource.py` and all 73 existing compressed episode records in `results/g1_pipeline_v1`. It ran no task world and added no fixture. G1 diagnostics must remain separate from G2: their worlds, teacher logs, diagnostic learned weights and optimizer states are not G2 demonstration/training/selection data or starting checkpoints.

## Recomputed evidence

- 24 unique registered G1 worlds, 73 executions: teacher 24, BC 24, same-candidate greedy 24, PPO on-policy probe 1 on a repeated G1 world. There was no Q deployment world in this batch.
- 15,593 actual backend calls = 73 enter + 13,155 measure + 2,292 clear + 73 exit. Measure/clear alone are 15,447. Attempted calls and accepted ledger events matched here, with zero extra/rejected attempts.
- Every compressed SHA256 and uncompressed-content SHA256 matched its stored ledger entry. Recomputed `prefix + sum(macro deltas) + tail` exactly matched terminal environment time for every episode (max difference 0 seconds).
- All 73 saved terminal labels indicate success and agree with raw completion fields and actual cleared/source counts. The independent validator reads true N only after the policy returns; terminal truth stays beside raw snapshots.
- A recursive scan of the 2,237 saved online snapshots found no true_n/true_N, world_id, scenario, seed, stats, sources, source_count or normalized_reward fields. Code inspection also confirmed that selectors receive only the snapshot and four-call interface, not recipe or terminal labels.
- G1 optimizer steps were BC 24, Q MC 1, Q TD 1 and PPO 4. Q reused eight stored teacher episodes without extra interaction. PPO's diagnostic probe used one already registered G1 world; it is not a G2 run.
- BC diagnostic held-out decision accuracy changed from 45/343 to 124/343. Those 12 worlds are now exposed G1 diagnostic evidence, and their scenario groups differ from the first 12 BC training worlds. This is not a G2 selection score or a task-time improvement claim.

## Reporting boundaries and correction requested

The first saved teacher episode was recovered from the same complete gzip after a path-display exception, without reexecution. Its storage timing is unavailable, explicitly marked in its row. Consequently the aggregate storage_wall_s is a partial sum with one zero placeholder, not complete storage timing. The measured wall_time_s starts in the resumed invocation and does not include the earlier interrupted invocation; report that scope instead of claiming an exact full-stage end-to-end time. Saved per-execution time and calls still cover all 73 executions.

A post-execution durability issue was reported to root: the reviewed `common.execute` raises directly on accepted-event/call or terminal-cost validation disagreement before it constructs/returns the entry. A caller can therefore lose the just-executed trajectory and cost before saving or advancing its budget ledger. Current G1 has no such mismatch, so its saved evidence is unaffected. Before G2, validation failures should be preserved in a failed entry (or an exception carrying that entry), then persisted and charged before stopping. This audit did not edit the coordinator's files.

The reviewed results are local CPU diagnosis, not official validation, an unconditional deadline guarantee, an RL performance result, or completed G2 training. The observed process peak was 379.390625 MiB; it does not establish the memory requirements of full 512-episode demonstration storage or the future replay corpus.
