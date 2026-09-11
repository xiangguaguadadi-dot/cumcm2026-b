# BC and complete-episode MC PPO

## Current status: G2 and checkpoint selection completed

2026-09-11. The coordinator's unified runner completed the shared 512-episode C7 corpus, three independently initialized BC models, and all three PPO training runs through 1,024 new episodes each. Actual environment collection and training were performed by that unified runner; this component agent has no pending independent training run.

PPO did **not** meet the preregistered promotion gate for either question. After selecting each initialization's complete checkpoint separately, its three-initialization mean was 244.977 seconds/source for Q3 and 464.389 seconds/source for Q4, respectively 3.836% and 5.569% slower than original C7 on the shared selection worlds. Q4 was about 1.010% faster than corresponding BC, with a negative paired-difference interval, but missed the 2% gate and remained slower than C7. No default C7 replacement is authorized.

The final values, all checkpoint positions and failure lists are in the [selection summary](../analysis/selection_result/selection_summary.json) and [selection report](../analysis/selection_result/REPORT.md). The [independent row-statistics review](../verification/selection_independent_review.md) rechecked all 5,760 saved selection rows and 32 paired intervals without new sampling. These are local checkpoint-selection results with selection bias, not a blind final test or official Windows validation.

The G0/G1 notes below preserve the historical implementation and validation process. Statements describing an earlier wait for G2 are superseded by this completed status.

This implementation belongs to the newly authorized `20260911_rl_execution` phase. It imports the common `shared.CandidateNetwork`/`batch_snapshots`; it creates no environment, world, source generator, network architecture, dependency installation or private demonstration corpus.

## Integration

Run from the execution directory (or add that directory to `PYTHONPATH`):

```python
from shared import CandidateNetwork
from ppo.trainer import BCTrainer, PPOTrainer, episode_from_core

bc = BCTrainer(CandidateNetwork(), seed=0)
bc_metrics = bc.update(shared_c7_raw_episodes)
# Pure C7 labels are each recorded selected index, checked against teacher_index.
# Copy/save bc.model.state_dict() for the separate BC deployment baseline and Q support.

ppo = PPOTrainer(CandidateNetwork(), seed=0)
ppo.model.load_state_dict(bc.model.state_dict())
selector = lambda snapshot: ppo.select(snapshot).as_core_choice()
# Root runs core.run_episode(..., selector), then checks actual environment stats.
# true_N is supplied only after that terminal validation.
training_episode = episode_from_core(validated_raw_episode, true_n=true_N)
metrics = ppo.update([training_episode])
# Deployment chooses deterministically and records sampled=False.
deployment_selector = lambda snapshot: ppo.select(snapshot, deterministic=True).as_core_choice()
```

For a policy batch, collect every episode under the same unchanged trainer version before calling update. Stale or mixed policy versions are rejected. The first update pass also verifies saved old probabilities and values against the current model (absolute tolerance 2e-4, relative 1e-5), so independently initialized trainers with coincident version counters cannot silently share rollouts. `Choice` holds a canonical immutable full snapshot; its metadata includes the snapshot digest, old action log probability, old observable value and policy version. Core retains the detached full snapshot. Updating verifies its digest, action index and original mask; candidate regeneration or mutation is rejected. Teacher index and payload metadata never enter shared network tensors.

`state_dict()`/`load_state_dict()` include model, Adam state, policy version, CPU sampling RNG and exact trainer configuration. The returned checkpoint recursively clones every tensor onto CPU and copies optimizer/RNG/configuration, so keeping it in memory cannot alias future live training updates. Root owns checkpoint paths, data and experiment manifests. For transferring BC weights to PPO/Q use only the common model weights; do not load a BC trainer checkpoint as a PPO trainer checkpoint.

## Objective and termination

`episode_from_core(raw, true_n=...)` accepts only completed episodes with explicit success labels. Root must overwrite an apparently successful raw result if the independent terminal validator detects remaining sources or other actual failure. Real deadline/error is a failed terminal; artificial truncation is rejected and must be resumed. The first implementation does not bootstrap.

MC costs are computed from the disjoint raw `decision.delta_time_s` and `tail_time_s`. A fallback tail already folded into the final macro must be passed as zero explicit tail. Prefix cost before the first selector decision remains in the whole-episode ledger but is independent of all subsequent choices. Costs after any sampled decision include later forced actions and fallback. They are normalized once by `1000 * terminal_true_N`; a real failure subtracts 100 once. A fallback-only episode has no policy rows. Finite failure penalties do not guarantee zero-failure optimality; the separate reliability gate remains mandatory.

PPO uses gamma 1, complete MC returns, fixed old-value advantages, clip 0.2, 4 epochs, Adam 3e-4 and gradient norm 0.5. There is no GAE, GRU, entropy bonus, advantage whitening or shaping. Actor loss is mean of episode sums over actual sampled policy decisions. Microbatches accumulate the full episode-equal gradient before each optimizer step, so long episodes are not divided by their length. Value regression is mean of per-episode decision means; advantages are detached. The shared backbone is optimized once per epoch with `actor_loss + 0.5 * value_loss`; this standard joint-loss implementation is an explicit engineering choice, while value gradients do not pass through actor advantages.

BC uses episode-equal mean cross entropy on pure C7 demonstrations, default 4 epochs with Adam 3e-4 and gradient norm 0.5. It accepts no terminal N. Every actual label must match that snapshot's teacher index and be valid. The BC state-value head is not fitted by imitation; the PPO MC loss trains it later. Q can freeze a separate copy of the common BC candidate scoring path.

## Historical G0 validation and its evidence limit

16 synthetic fixtures have passed on the isolated Python/PyTorch 2.8.0 CPU runtime: 8 scalar return/weight checks and 8 real shared-network fixtures. They include tail accounting, one-time failure/N scaling, rejection of artificial truncation, actual-action-only gradients, snapshot mutation, masked zero probability and gradients, finite PPO update, stale-rollout rejection, BC improvement on a constructed classification fixture and invariant gradient aggregation across microbatch sizes.

These are correctness fixtures with zero task worlds and zero environment interactions. They are not evidence of improvement over C7, resource feasibility, MPS compatibility or actual successful task completion. At this historical G0 stage, real collection/training awaited the coordinator's G0/G1 gate; G2 has since completed as recorded above.

```bash
python -m unittest discover -s tests -p 'test_ppo*.py' -v
```


## Preregistered G2 minibatch plan (implemented; fixed before selection results)

- The one shared corpus has 512 pure C7 episodes. For each of the three training initializations, initialize the common network independently, shuffle the same corpus with its registered training seed, and run 8 complete passes in batches of 8 episodes with `BCConfig(epochs=1)`. This is 64 batches per pass and 512 Adam steps per initialization, rather than four Adam steps on one giant full-corpus batch. The corpus is shared data, not three newly collected corpora. Preserve each corresponding BC model as a deployment baseline and as that initialization's common PPO/Q starting point. If only one BC weight set is used with three later sampling seeds, report that narrower design explicitly rather than calling it three independent initial networks.
- PPO collects batches of 8 complete episodes under one unchanged current policy, then calls `update` once with `PPOConfig(epochs=4)`. All actual policy decisions in those episodes contribute to the episode-equal summed actor loss. The 128-row forward microbatches only limit activation memory; they do not create extra optimizer steps or change episode weights. Default update size is therefore 4 Adam steps per 8 new episodes.
- Checkpoint positions are fixed at 128, 256, 512 and 1024 newly executed training episodes per initialization, subject to the existing primitive cap and reserved completion budget. No extra checkpoint is selected after inspecting results. If the cap stops a run before a planned point, save the actual stop state for provenance but do not silently make it a fifth selection evaluation. An incomplete episode is resumed or classified as a real failure by the coordinator; it is not a cheap terminal label. A final batch of fewer than 8 completed episodes may be updated with its actual episode denominator and must be reported as such.
- All BC/PPO weights and data ordering seeds were registered by the coordinator. Terminal N stays in label construction, not an online feature. BC and PPO gradient steps, task interactions, failed episodes, fallback costs and selection evaluations are separate ledger entries. G2 collection was performed by the unified runner after the G0/G1 gate; this agent did not collect a separate corpus.

## Read-only audit of the common network

The common implementation was read directly. Only the three feature arrays and valid mask reach neural tensors; teacher labels, candidate payloads and terminal truth metadata are excluded by explicit lookup. Each candidate attends over the observable 20-channel rows independently, so padded/invalid candidates cannot contaminate the other candidate encodings. Invalid scores become negative infinity, and the probability/loss paths only gather valid recorded actions. The model contains no GRU, graph propagation, positional candidate-index embedding or environment lookup. This is a light candidate scorer with channel attention, not the original large graph/recurrent proposal.

Two boundaries were reported to root without editing shared.py. First, its initial batching implementation cast `valid_mask` directly to bool: malformed nonboolean entries such as integer 2 could become true. Root fixed this before G2 by validating explicit booleans before the cast; normal core snapshots already produce booleans. Second, the value head sees global features and pooled channel features, but not candidate features/mask. It is therefore a legal observable baseline with a deliberately narrower input than the scoring path, not an exact full-snapshot conditional value or a proof of Markov sufficiency. This may affect variance/fit and is an empirical limitation, not a policy-gradient identity error. Feature-generation nonleakage remains a separate core/runner data-flow responsibility; a neural whitelist alone does not prove how those features were constructed.

## Historical G1 integration status

Root completed the separate G1 diagnosis: 24 registered worlds, 73 executions, 15,593 calls and zero failures. It includes actual BC24/Q-MC1/Q-TD1/PPO4 diagnostic optimizer steps; therefore “no training has occurred” is not an accurate global statement. These G1 diagnostic data/weights remained excluded from G2. This agent independently audited all existing raw files, hashes, cost partitions and online snapshot label separation without running a new world; see G1_AUDIT.md. At the time of that audit, the full PPO three-initialization G2 run awaited the coordinator; its subsequent completion is recorded at the top of this file.
