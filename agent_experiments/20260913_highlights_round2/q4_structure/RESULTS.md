# Q4 source-structure results

## Validated highlight A: maximum-count stopping certificate

Q4 states that source channels are distinct and that there are at most 16 sources. Therefore, as soon as 16 distinct channels have produced a positive observation or a successful clear, every still-unseen channel is certified absent. Pending discovered sources must still be cleared; only remaining discovery stations may be removed.

The unchanged C7 candidate was paired with the identical candidate configured with `upper_bound_stop=False`. On all 1,200 exposed frozen-v1 Q4 worlds (2,400 executions), both arms cleared all 15,550 sources and exited normally. The certificate reduced mean time from **466.502815 to 452.760907 s/source**, a paired difference of **-13.741908 s/source** (2.946%); the preregistered 5,000-resample world-bootstrap 95% interval was **[-15.906026, -11.653622]**. It removed 1,694 station visits, 7,000 measurements, 6,068 channel switches, and about 1,116 km of travel.

The effect is structurally sparse: all 970 worlds with 10--15 sources tied exactly. Among 230 sixteen-source worlds, 224 improved, five tied, and one regressed. The sole regression was `LOCAL-v1-q4-edge_mixed_min_radius-5016`, by 0.114859 s/source: stopping one station earlier changed the later localization route enough to add two measurements, even though it traveled 45.8 m less. Thus the certificate is safe and strongly beneficial on average, but early stopping does not pointwise dominate because discovery and localization are jointly routed.

On 24 constructed 16-source edge/orientation pressure worlds (48 executions), both arms again fully cleared. Count stopping improved by **8.376122 s/source**, bootstrap 95% **[-13.305611, -4.142979]**, with 14 improvements, 10 ties, and no regression.

## Validated highlight B: continuous post-clear antenna-heading certificate

Let `c` be a successful clear point, so the true source `s` obeys `|s-c|<=20 m`. For every earlier positive receive point `p`, a directional heading `h` must satisfy `h·(p-s)>=0`. Replacing unknown `s` by `c` and widening the corresponding heading semicircle by `asin(20/|p-c|)` gives a conservative continuous arc. Intersecting all arcs produces a certified feasible heading set. An empty intersection rules out every directional half-plane and therefore certifies an omnidirectional source under the stated model.

Across the count-stop arm's 7,885 directional sources in the full closed loop, **7,885/7,885 true headings were retained** and zero feasible sets were empty. Median feasible width was **139.213 degrees**; 599 sources narrowed to at most 60 degrees, 1,445 to at most 90 degrees, and 2,783 to at most 120 degrees. Among 7,665 omni sources, 43 produced an empty interval: empirical precision was 100% because no directional source was rejected, but recall was only **0.561%**. This is useful as a safe orientation/omni certificate, not a strong omni classifier.

A separate preregistered constructed stress run checked 100,000 directional configurations, including 29,445 positive sites exactly on the emission half-plane boundary, with random successful-clear errors up to 20 m. It excluded zero true headings. A deliberately surrounding three-site construction certified all 1,000/1,000 omni cases. This is analytic construction pressure, not closed-loop or official evidence.

## Evidence boundary and failed routes

- Frozen-v1 is an already exposed local regression suite using an assumed simulator distribution. Pressure cases are constructed. No blind set or official Windows simulator was run.
- The heading auditor reads truth only after solver completion to score containment. The C7 solver never receives truth.
- Empty heading intersection has a one-way interpretation: it certifies omni under the model. A nonempty interval cannot certify directionality, which explains the low omni recall.
- Maximum-count stopping was already enabled in C7; this experiment isolates and quantifies it as a modeling highlight rather than introducing a new deployed solver.
- The observed one-world time regression prevents a claim of pointwise speed dominance.

## Reproduction

From `代码/` with Python 3.12:

```bash
python3.12 -S agent_experiments/20260913_highlights_round2/q4_structure/run_experiment.py --suite quick --out quick_repro
python3.12 -S agent_experiments/20260913_highlights_round2/q4_structure/run_experiment.py --suite full --out full_repro
python3.12 -S agent_experiments/20260913_highlights_round2/q4_structure/run_experiment.py --suite pressure --out pressure_repro
python3.12 -S agent_experiments/20260913_highlights_round2/q4_structure/continuous_stress.py --cases 100000 --out agent_experiments/20260913_highlights_round2/q4_structure/continuous_stress_repro.json
python3.12 -S agent_experiments/20260913_highlights_round2/q4_structure/verify_outputs.py
```

Raw paired rows and per-source continuous intervals are in each run's `rows.jsonl`; registrations contain the runner, C7, case, and frozen-manifest hashes.
