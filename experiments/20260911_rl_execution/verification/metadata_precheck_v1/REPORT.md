# RL evidence consistency audit

Status: **consistent_partial**; mode: `metadata_only`.

Errors: 0; pending findings: 97; unknown-cost records: 35.

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
| selection/ppo_init81001_ep1024 | 190 | 190 | 36627 |
| selection/bc_init81002 | 192 | 192 | 37368 |
| selection/ppo_init81002_ep0128 | 192 | 192 | 37857 |
| selection/ppo_init81002_ep0256 | 192 | 192 | 37494 |
| selection/ppo_init81002_ep0512 | 192 | 192 | 36864 |
| selection/ppo_init81002_ep1024 | 192 | 192 | 36996 |
| selection/q_init81002_ep0128 | 17 | 17 | 3442 |
| selection/bc_init81003 | 107 | 107 | 20868 |
| selection | 192 | 2618 | 509822 |

Repeated initializations are paired observations of the same selection world. The registered selection population is 192 worlds (96 per question), regardless of the number of models.

## Teacher wrapper versus original C7

Trace comparison: **not_checked_metadata_only**. Checked 0 paired worlds; equal semantic traces: 0; equal virtual costs: 0.

Only `real_timestamp_ms` and `remaining_real_duration_s` are omitted from response equality. Wall time is not compared. Differences and their first mismatching request are retained in the JSON report.

## Findings

- **pending / missing_future_file** — `results/g2_selection/models/ppo_init81001_ep1024/summary.json`: "Not produced yet."
- **pending / stage_incomplete** — `selection/ppo_init81001_ep1024`: {"rows": 190, "expected_or_cap": 192}
- **pending / selection_model_not_started** — `q_init81001_ep0128`: {"model_id": "q_init81001_ep0128", "algorithm": "q", "seed": 81001, "checkpoint": {"algorithm": "q", "seed": 81001, "episodes": 128, "path": "results/g2/init_81001/q/checkpoints/episode_0128.pt", "sha256": "3c6d0c1e3f73aea23604c4f387067348015ed16f4121a28f2ed7933158136ccb"}}
- **pending / selection_model_not_started** — `q_init81001_ep0256`: {"model_id": "q_init81001_ep0256", "algorithm": "q", "seed": 81001, "checkpoint": {"algorithm": "q", "seed": 81001, "episodes": 256, "path": "results/g2/init_81001/q/checkpoints/episode_0256.pt", "sha256": "71e49504c0bd3e2644d320feb6441b4141dbc7d7595d4bcdf6c85fa09fadf8b6"}}
- **pending / selection_model_not_started** — `q_init81001_ep0512`: {"model_id": "q_init81001_ep0512", "algorithm": "q", "seed": 81001, "checkpoint": {"algorithm": "q", "seed": 81001, "episodes": 512, "path": "results/g2/init_81001/q/checkpoints/episode_0512.pt", "sha256": "2873a2517099ab88669fd0c3198484f002ac29b2b363b35901b2717841717064"}}
- **pending / selection_model_not_started** — `q_init81001_ep1024`: {"model_id": "q_init81001_ep1024", "algorithm": "q", "seed": 81001, "checkpoint": {"algorithm": "q", "seed": 81001, "episodes": 1024, "path": "results/g2/init_81001/q/checkpoints/episode_1024.pt", "sha256": "9483208dabe02e0440583ff12b82c98be2df34710f18159f26ed78bdd54f751a"}}
- **pending / missing_future_file** — `results/g2_selection/models/q_init81002_ep0128/summary.json`: "Not produced yet."
- **pending / stage_incomplete** — `selection/q_init81002_ep0128`: {"rows": 17, "expected_or_cap": 192}
- **pending / selection_model_not_started** — `q_init81002_ep0256`: {"model_id": "q_init81002_ep0256", "algorithm": "q", "seed": 81002, "checkpoint": {"algorithm": "q", "seed": 81002, "episodes": 256, "path": "results/g2/init_81002/q/checkpoints/episode_0256.pt", "sha256": "80c0b7f09142f66768f02f7fcf144726546c22fcac696184f0d0ede22e39e408"}}
- **pending / selection_model_not_started** — `q_init81002_ep0512`: {"model_id": "q_init81002_ep0512", "algorithm": "q", "seed": 81002, "checkpoint": {"algorithm": "q", "seed": 81002, "episodes": 512, "path": "results/g2/init_81002/q/checkpoints/episode_0512.pt", "sha256": "880cde8a357d841cd9aa8dd361fc35e42b5e961d846b6ad0c7eabb97b3c5d95b"}}
- **pending / selection_model_not_started** — `q_init81002_ep1024`: {"model_id": "q_init81002_ep1024", "algorithm": "q", "seed": 81002, "checkpoint": {"algorithm": "q", "seed": 81002, "episodes": 1024, "path": "results/g2/init_81002/q/checkpoints/episode_1024.pt", "sha256": "6294fd7cca2469a67b0688c98685561299e9b6b6e1f296d922ada0ed24c0170d"}}
- **pending / missing_future_file** — `results/g2_selection/baselines/bc_init81003/summary.json`: "Not produced yet."
- **pending / stage_incomplete** — `selection/bc_init81003`: {"rows": 107, "expected_or_cap": 192}
- **pending / selection_model_not_started** — `ppo_init81003_ep0128`: {"model_id": "ppo_init81003_ep0128", "algorithm": "ppo", "seed": 81003, "checkpoint": {"algorithm": "ppo", "seed": 81003, "episodes": 128, "path": "results/g2/init_81003/ppo/checkpoints/episode_0128.pt", "sha256": "e7065172ce712f7d54b9dd22c52cca1bbbfc346c9eaec0f8d482161b02ec7679"}}
- **pending / selection_model_not_started** — `ppo_init81003_ep0256`: {"model_id": "ppo_init81003_ep0256", "algorithm": "ppo", "seed": 81003, "checkpoint": {"algorithm": "ppo", "seed": 81003, "episodes": 256, "path": "results/g2/init_81003/ppo/checkpoints/episode_0256.pt", "sha256": "7b06ea91beafbf7130351cfbff4465f4c536467365bfed44734c7fe79849f4fb"}}
- **pending / selection_model_not_started** — `ppo_init81003_ep0512`: {"model_id": "ppo_init81003_ep0512", "algorithm": "ppo", "seed": 81003, "checkpoint": {"algorithm": "ppo", "seed": 81003, "episodes": 512, "path": "results/g2/init_81003/ppo/checkpoints/episode_0512.pt", "sha256": "35bcbb0a09f1ad6543829115ff407a383529828b1031c53c7d877075b808adcb"}}
- **pending / selection_model_not_started** — `ppo_init81003_ep1024`: {"model_id": "ppo_init81003_ep1024", "algorithm": "ppo", "seed": 81003, "checkpoint": {"algorithm": "ppo", "seed": 81003, "episodes": 1024, "path": "results/g2/init_81003/ppo/checkpoints/episode_1024.pt", "sha256": "7444aedcc0fef8fadd1fab5b663a55e8991103e6b843cd6fcaccb18929962db4"}}
- **pending / selection_model_not_started** — `q_init81003_ep0128`: {"model_id": "q_init81003_ep0128", "algorithm": "q", "seed": 81003, "checkpoint": {"algorithm": "q", "seed": 81003, "episodes": 128, "path": "results/g2/init_81003/q/checkpoints/episode_0128.pt", "sha256": "efa2d9a46776523501b72a7725f1962eb3412c7a81bd94eb2bc66cb14781e896"}}
- **pending / selection_model_not_started** — `q_init81003_ep0256`: {"model_id": "q_init81003_ep0256", "algorithm": "q", "seed": 81003, "checkpoint": {"algorithm": "q", "seed": 81003, "episodes": 256, "path": "results/g2/init_81003/q/checkpoints/episode_0256.pt", "sha256": "dd5cc0551ca9d400a49c6d1fbec703eedfbcadbca236afa749a0d7ac2cc30f15"}}
- **pending / selection_model_not_started** — `q_init81003_ep0512`: {"model_id": "q_init81003_ep0512", "algorithm": "q", "seed": 81003, "checkpoint": {"algorithm": "q", "seed": 81003, "episodes": 512, "path": "results/g2/init_81003/q/checkpoints/episode_0512.pt", "sha256": "e73bc4c95ad0d9af141ed1c873956790c32202e1f86de14992d7c4d6d49e6423"}}
- **pending / selection_model_not_started** — `q_init81003_ep1024`: {"model_id": "q_init81003_ep1024", "algorithm": "q", "seed": 81003, "checkpoint": {"algorithm": "q", "seed": 81003, "episodes": 1024, "path": "results/g2/init_81003/q/checkpoints/episode_1024.pt", "sha256": "b399478c9cc39cc47ae88a28cc4c35639b8c21b13ddb02d89e745973c5997676"}}
- **pending / orphan_archive_needs_reconciliation** — `results/g2_selection/models/q_init81002_ep0128/episodes/q3_0010.json.gz`: {"path": "results/g2_selection/models/q_init81002_ep0128/episodes/q3_0010.json.gz", "status": "archive_without_index", "calls": null}
- **pending / orphan_archive_needs_reconciliation** — `results/g2_selection/models/q_init81002_ep0128/episodes/q4_0010.json.gz`: {"path": "results/g2_selection/models/q_init81002_ep0128/episodes/q4_0010.json.gz", "status": "archive_without_index", "calls": null}
- **pending / orphan_archive_needs_reconciliation** — `results/g2_selection/models/q_init81002_ep0128/episodes/q3_0009.json.gz`: {"path": "results/g2_selection/models/q_init81002_ep0128/episodes/q3_0009.json.gz", "status": "archive_without_index", "calls": null}
- **pending / orphan_archive_needs_reconciliation** — `results/g2_selection/models/q_init81002_ep0128/episodes/q4_0009.json.gz`: {"path": "results/g2_selection/models/q_init81002_ep0128/episodes/q4_0009.json.gz", "status": "archive_without_index", "calls": null}
- **pending / orphan_archive_needs_reconciliation** — `results/g2_selection/models/q_init81002_ep0128/episodes/q4_0008.json.gz`: {"path": "results/g2_selection/models/q_init81002_ep0128/episodes/q4_0008.json.gz", "status": "archive_without_index", "calls": null}
- **pending / orphan_archive_needs_reconciliation** — `results/g2_selection/models/q_init81002_ep0128/episodes/q4_0011.json.gz`: {"path": "results/g2_selection/models/q_init81002_ep0128/episodes/q4_0011.json.gz", "status": "archive_without_index", "calls": null}
- **pending / orphan_archive_needs_reconciliation** — `results/g2_selection/models/q_init81002_ep0128/episodes/q3_0011.json.gz`: {"path": "results/g2_selection/models/q_init81002_ep0128/episodes/q3_0011.json.gz", "status": "archive_without_index", "calls": null}
- **pending / orphan_archive_needs_reconciliation** — `results/g2_selection/models/q_init81002_ep0128/episodes/q3_0013.json.gz`: {"path": "results/g2_selection/models/q_init81002_ep0128/episodes/q3_0013.json.gz", "status": "archive_without_index", "calls": null}
- **pending / orphan_archive_needs_reconciliation** — `results/g2_selection/models/q_init81002_ep0128/episodes/q3_0012.json.gz`: {"path": "results/g2_selection/models/q_init81002_ep0128/episodes/q3_0012.json.gz", "status": "archive_without_index", "calls": null}
- **pending / orphan_archive_needs_reconciliation** — `results/g2_selection/models/q_init81002_ep0128/episodes/q4_0012.json.gz`: {"path": "results/g2_selection/models/q_init81002_ep0128/episodes/q4_0012.json.gz", "status": "archive_without_index", "calls": null}
- **pending / orphan_archive_needs_reconciliation** — `results/g2_selection/models/ppo_init81001_ep1024/episodes/q4_0095.json.gz`: {"path": "results/g2_selection/models/ppo_init81001_ep1024/episodes/q4_0095.json.gz", "status": "archive_without_index", "calls": null}
- **pending / orphan_archive_needs_reconciliation** — `results/g2_selection/models/ppo_init81001_ep1024/episodes/q3_0095.json.gz`: {"path": "results/g2_selection/models/ppo_init81001_ep1024/episodes/q3_0095.json.gz", "status": "archive_without_index", "calls": null}
- **pending / orphan_archive_needs_reconciliation** — `results/g2_selection/models/q_init81001_ep0128/episodes/q3_0000.json.gz`: {"path": "results/g2_selection/models/q_init81001_ep0128/episodes/q3_0000.json.gz", "status": "archive_without_index", "calls": null}
- **pending / orphan_archive_needs_reconciliation** — `results/g2_selection/models/q_init81001_ep0128/episodes/q4_0000.json.gz`: {"path": "results/g2_selection/models/q_init81001_ep0128/episodes/q4_0000.json.gz", "status": "archive_without_index", "calls": null}
- 54 additional details are in the JSON report.

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
