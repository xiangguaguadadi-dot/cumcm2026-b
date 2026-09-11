# Shared schema v1

`from core import run_episode, teacher_selector`; `from core.schema import GLOBAL_DIM, CHANNEL_DIM, CANDIDATE_DIM`.

`run_episode(env, mode, selector)` accepts only enter/measure/clear/exit. The selector receives a detached JSON-compatible snapshot and returns an integer index or `{index, metadata}`. All snapshots are recorded before execution; caller mutation cannot alter the engine's retained candidate payload.

Dimensions: G=16, 20 channels × C=12, K candidates × F=16, K≤64. Exact ordered names are in schema.py. Shared network consumes only three feature arrays and valid_mask. teacher_index is a BC label/hand-coded support-gate anchor, never a feature. Candidates are sorted by stable payload identity, not teacher rank.

Snapshot keys: schema_version, generator_version, decision_id, state_version, global_features, channel_features, candidate_features, valid_mask, candidate_ids, teacher_index, candidates. Candidate payload carries kind, index/channel, target, route_successor, stage, state_version, service_state and stop_contract. No true N, sources, seed, scenario identifier, privileged reward or environment object.

Whole-episode result: decisions with retained snapshot/index/metadata/delta_time_s/event_range; accepted interface events; terminal/success/error; fallback_reason; tail_time_s. A decision delta ends exactly at macro completion or takeover. tail_time_s starts at takeover and includes independent fallback only, so it never overlaps a decision delta. Normal deterministic exit has zero cost. If failure occurs before any decision, costs remain in prefix_time_s/tail_time_s and no synthetic learning choice is invented. Root supplies true N after termination and performs reward labels.

Source/clear geometry summaries are observable but compressed and not proved Markov. Candidate target and immediate cost are ranking proxies; C7 may execute several measurements and heuristic clears within one service macro. Only actual interface events determine training costs.
