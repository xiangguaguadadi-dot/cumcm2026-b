# Q3 compensated station geometry, mechanism 2

New files `compensated_arcs.py` and `compensated_engine.py` leave the P1
`engine.py`, `continuous.py`, and package entry unchanged. The new grammar
moves one future station inward toward a public source task while moving its
1–3 adjacent future companions outward. Their angles change jointly so their
boundary detection arcs continue to cover the sector. Actual past positions
remain fixed. The trigonometric arc construction is a proposal only; every
plan still needs the independent integer continuous certificate.

On the same 48 detached public Q3 prefixes, the 2/3/4 grammar generated 4863
finite layouts. Of these, 129 had both positive complete task-route proxy
improvement and positive coordinate gain under that same route; all 129
certified, covering 22/48 prefixes. The previous simple attraction grammar
provided plans on 6/48 prefixes. These are geometry feasibility/selection-proxy
diagnostics, **not actual closed-loop improvements**, and do not use future
P1 outcomes. This diagnostic run took 1.837 s and made zero environment calls.

`diagnostics.json` retains every prefix's counts and all positive certified
layout proxy summaries, input/source hashes, and data-role declaration. It
must not serve as an online lookup table; the executable recomputes proposals
from its actual public snapshot.

The full fixed-state proxy is movement along a two-opt open tour containing
all remaining paid discovery stations and all public source-task anchors,
divided by 5 m/s, plus 5 s for every assigned unknown-channel measure and 1 s
for every modeled channel switch. Localization branches, stochastic discovery,
known-channel retests, optical failures and their true exit positions remain
unmodeled. `coordinate_gain_same_order_s` evaluates the changed coordinates
against original coordinates under the exact same candidate order;
`route_gain_old_geometry_s` isolates the route-order component. Neither is a
real seconds/source score, and future full-run costs include all these omitted
branches through the real runner.

Integrated A-only entry:
`experiments/jointplan_v1/geometry/candidate_compensated_a_only.py`.
Defaults: `jointplan_geometry=True`, `jointplan_mixed=False`, the same P2
natural-boundary/intervention limits as the integrated A executor,
`jointplan_geometry_options={block_sizes:[2],max_plans:6,max_seconds:.35}`.
For block-size expansions use `[3]` and `[4]` as separately registered variants.
The source-defined provider is `compensated_engine`; Q4 dispatches unchanged to
the old geometry generator. Setting `jointplan_mixed=True` permits the B
selector for a later A+B ablation without altering the geometry grammar.

Validation: 19 pure tests pass, including jointly inward/outward certified
2/3/4 moves, no reconstruction of missing nonpublic stations, and preventing
Q4 from using the Q3 circle-arc shortcut. Tests reset the pure geometry cache
between cases so the diagnostic unknown/counterexample label is not sensitive
to prior test execution order. No actual environment test was run by Agent A.
