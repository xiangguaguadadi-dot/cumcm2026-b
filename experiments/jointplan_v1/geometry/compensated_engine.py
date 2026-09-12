"""Second geometry grammar: compensated Q3 boundary arcs.

Separate module leaves the frozen P1 v1 generator unchanged. This is a complete
public proposal API; Q4 uses the existing certified generator unchanged.
"""
import time
try:
    from .engine import _base_plan, proxy_cost, verify, propose as original_propose
    from .continuous import canonical_hash
    from .compensated_arcs import propose_compensated
except ImportError:
    from engine import _base_plan, proxy_cost, verify, propose as original_propose
    from continuous import canonical_hash
    from compensated_arcs import propose_compensated


def propose(snapshot, options=None, diagnostics=None):
    options = options or {}
    if snapshot['mode'] != 3:
        return original_propose(snapshot, options, diagnostics)
    started = time.perf_counter()
    deadline = started + options.get('max_seconds', .35)
    base = _base_plan(snapshot)
    base_cost = proxy_cost(snapshot, base['stations'])
    verify(snapshot, base, deadline=deadline)
    candidates = propose_compensated(snapshot, base, options.get('block_sizes', [2]))
    ranked = []
    for plan in candidates:
        plan['proxy'] = proxy_cost(snapshot, plan['stations'])
        same_order = proxy_cost(snapshot, base['stations'], plan['proxy']['route'])
        plan['coordinate_gain_same_order_s'] = same_order['total_s'] - plan['proxy']['total_s']
        plan['route_gain_old_geometry_s'] = base_cost['total_s'] - same_order['total_s']
        plan['proxy_gain_s'] = base_cost['total_s'] - plan['proxy']['total_s']
        if (plan['coordinate_gain_same_order_s'] > options.get('minimum_coordinate_gain_s', 1e-7)
                and plan['proxy_gain_s'] > options.get('minimum_proxy_gain_s', 0.)):
            ranked.append(plan)
    ranked.sort(key=lambda p: (-p['proxy_gain_s'], canonical_hash(p['stations'])))
    plans, statuses, attempts, seen = [], {}, 0, set()
    for plan in ranked:
        if time.perf_counter() >= deadline or len(plans) >= options.get('max_plans', 6):
            break
        key = canonical_hash(plan['stations'])
        if key in seen:
            continue
        seen.add(key)
        attempts += 1
        certificate = verify(snapshot, plan, deadline=deadline)
        statuses[certificate['status']] = statuses.get(certificate['status'], 0) + 1
        if certificate['status'] != 'certified':
            continue
        plan['certificate'] = certificate
        plan['route_station_ids'] = [key for kind, key in plan['proxy']['route'] if kind == 'station']
        plan['geometry_grammar'] = 'compensated_boundary_arcs_v2'
        plan['generation'] = {'seconds': time.perf_counter() - started, 'attempts': attempts, 'statuses': dict(statuses), 'proposed_candidates': len(candidates)}
        plans.append(plan)
    if diagnostics is not None:
        diagnostics.update({'seconds': time.perf_counter() - started, 'attempts': attempts, 'statuses': statuses, 'proposed_candidates': len(candidates), 'positive_proxy_candidates': len(ranked), 'certified_plans': len(plans), 'time_limit_reached': time.perf_counter() >= deadline})
    return plans
