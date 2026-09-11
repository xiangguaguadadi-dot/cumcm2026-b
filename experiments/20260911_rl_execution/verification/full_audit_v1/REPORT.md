# RL evidence consistency audit

Status: **consistent_complete**; mode: `archives`.

Errors: 0; pending findings: 0; unknown-cost records: 0.

| Stage | Unique worlds | Executions | Known business calls |
|---|---:|---:|---:|
| g0_results_v1 | 20 | 60 | 67853 |
| g0_audit_v1 | 20 | 60 | 11300 |
| g1 | 24 | 73 | 15593 |
| shared_demonstrations | 512 | 512 | 101955 |
| train/81001/ppo | 1024 | 1024 | 205618 |
| train/81001/q | 1024 | 1024 | 678955 |
| train/81002/ppo | 1024 | 1024 | 204523 |
| train/81002/q | 1024 | 1024 | 681238 |
| train/81003/ppo | 1024 | 1024 | 203585 |
| train/81003/q | 1024 | 1024 | 678104 |
| selection/original_c7 | 192 | 192 | 37627 |
| selection/teacher_wrapper | 192 | 192 | 37627 |
| selection/same_candidates_greedy | 192 | 192 | 36736 |
| selection/bc_init81001 | 192 | 192 | 37508 |
| selection/ppo_init81001_ep0128 | 192 | 192 | 37292 |
| selection/ppo_init81001_ep0256 | 192 | 192 | 37407 |
| selection/ppo_init81001_ep0512 | 192 | 192 | 38109 |
| selection/ppo_init81001_ep1024 | 192 | 192 | 36995 |
| selection/q_init81001_ep0128 | 192 | 192 | 36865 |
| selection/q_init81001_ep0256 | 192 | 192 | 37081 |
| selection/q_init81001_ep0512 | 192 | 192 | 37617 |
| selection/q_init81001_ep1024 | 192 | 192 | 36876 |
| selection/bc_init81002 | 192 | 192 | 37368 |
| selection/ppo_init81002_ep0128 | 192 | 192 | 37857 |
| selection/ppo_init81002_ep0256 | 192 | 192 | 37494 |
| selection/ppo_init81002_ep0512 | 192 | 192 | 36864 |
| selection/ppo_init81002_ep1024 | 192 | 192 | 36996 |
| selection/q_init81002_ep0128 | 192 | 192 | 37364 |
| selection/q_init81002_ep0256 | 192 | 192 | 37453 |
| selection/q_init81002_ep0512 | 192 | 192 | 37059 |
| selection/q_init81002_ep1024 | 192 | 192 | 37295 |
| selection/bc_init81003 | 192 | 192 | 37245 |
| selection/ppo_init81003_ep0128 | 192 | 192 | 38205 |
| selection/ppo_init81003_ep0256 | 192 | 192 | 37759 |
| selection/ppo_init81003_ep0512 | 192 | 192 | 37077 |
| selection/ppo_init81003_ep1024 | 192 | 192 | 36786 |
| selection/q_init81003_ep0128 | 192 | 192 | 37198 |
| selection/q_init81003_ep0256 | 192 | 192 | 37501 |
| selection/q_init81003_ep0512 | 192 | 192 | 36994 |
| selection/q_init81003_ep1024 | 192 | 192 | 37233 |
| selection | 192 | 5760 | 1119488 |

Repeated initializations are paired observations of the same selection world. The registered selection population is 192 worlds (96 per question), regardless of the number of models.

## Teacher wrapper versus original C7

Trace comparison: **all_equal**. Checked 192 paired worlds; equal semantic traces: 192; equal virtual costs: 192.

Only `real_timestamp_ms` and `remaining_real_duration_s` are omitted from response equality. Wall time is not compared. Differences and their first mismatching request are retained in the JSON report.

## Findings

No consistency failures or unfinished records found in the selected audit scope.

## Evidence boundary

- Read-only evidence audit: zero world/policy executions and zero checkpoint deserializations.
- Metadata mode does not read/decompress episode bodies or establish online feature non-leakage.
- Archive mode checks saved snapshot keys, feature shapes, observable feature reconstruction and physical previous-macro seconds; this is not a formal information-flow proof.
- Checkpoint bytes are hashed against the registered indices; hidden tensor/trainer state requires the separate diagnostics.
- Original C7 retains its own summary schema. Its baseline_primitive_log supplies accepted request/response data for physical cost checks; no macro decisions are invented.
- Hashes detect changes relative to saved indices, not independent authenticity of self-generated data.
- Known costs are separate from pending/interrupted attempts. Missing actual cost is not zero.
- Training repetitions and initialization repetitions are executions, not independent world samples.
- No new blind or official validation is claimed. Historical G0 raw JSON is retained unchanged.
