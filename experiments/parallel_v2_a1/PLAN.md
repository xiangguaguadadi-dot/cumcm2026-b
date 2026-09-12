# Q3 trial-point decision geometry

Parent: A1 r2 (230.82141809866428 s/source, 2400 exposed Q3 cases).
All policy changes use only observed bearings/no-signal/failed-clear actions. The authoritative convex feasible set and certified-clear conditions remain inherited.
Direction: replace an uncertified optical trial at the minimum enclosing circle center with observation-conditioned expected hit/travel choices. On failure, measure at the actual trial point, saving needless return to the old estimate.
Round 1: polygon area centroid (uniform-area modeling hypothesis), no empirical parameters.
Round 2: optimize expected finite-hypothesis first-clear plus failed-clear continuation cost.
Round 3: refine only if prior trials demonstrate a credible mechanism; stop this direction at three consecutive non-improving rounds.
Development: new generated Q3 worlds, 12 registered noise/scenario groups, seeds 96212000-96212007, used for development only. No final holdout is created. Rules + quick per round, full + all 4800 exposed same-ID rows for retained candidates. All cases must finish normally and clear every source.
