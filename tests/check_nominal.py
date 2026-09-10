"""Read-only comparison with the supplied public specification, not official replay."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--package', required=True)
    p.add_argument('--out', required=True)
    args = p.parse_args()
    package = Path(args.package).resolve()
    sys.path.insert(0, str(package))
    from local_env import LocalEnv, Source

    checks = []

    def check(name, actual, expected, tolerance=None):
        ok = abs(actual-expected) <= tolerance if tolerance is not None else actual == expected
        checks.append(dict(name=name, passed=ok, actual=actual, expected=expected))

    def env(sources):
        e = LocalEnv(sources, keep_log=False)
        e.error = lambda x, y, channel: 0.0
        e.enter()
        return e

    # Isolate the physics using synthetic one-source unit cases. Benchmark cases
    # with valid counts and mixtures are handled by sensitivity.py separately.
    for name, source, point, expected in [
        ('omnidirectional_at_radius', Source(1, 0, 0, 1000), (1000, 0), 'direction'),
        ('omnidirectional_outside_radius', Source(1, 0, 0, 1000), (1000.001, 0), 'no_signal'),
        ('near_at_five', Source(1, 0, 0, 1000), (5, 0), 'near'),
        ('above_five', Source(1, 0, 0, 1000), (5.001, 0), 'direction'),
        ('directional_front', Source(1, 0, 0, 1000, 0), (500, 0), 'direction'),
        ('directional_back', Source(1, 0, 0, 1000, 0), (-500, 0), 'no_signal'),
        ('directional_positive_boundary', Source(1, 0, 0, 1000, 0), (0, 500), 'direction'),
        ('directional_negative_boundary', Source(1, 0, 0, 1000, 0), (0, -500), 'direction'),
        ('directional_back_even_inside_five', Source(1, 0, 0, 1000, 0), (-1, 0), 'no_signal'),
        ('outside_target_region_receiver', Source(1, 1800, 0, 1000), (2000, 0), 'direction'),
    ]:
        e = env([source])
        result = e.measure(*point, 1)
        check(name, result['measure_result'], expected)
        check(name+'_bearing_field', 'svd_deg' in result, expected == 'direction')

    for name, point, direction, expected, duration in [
        ('clear_at_twenty', (20, 0), None, 'success', 9.0),
        ('clear_outside_twenty', (20.001, 0), None, 'no_target_in_range', 7.0002),
        ('clear_from_directional_back', (-20, 0), 0.0, 'success', 9.0),
    ]:
        e = env([Source(1, 0, 0, 1000, direction)])
        result = e.clear(*point, 1)
        check(name, result['clear_result'], expected)
        check(name+'_time', result['virtual_time_s'], duration, 1e-6)

    e = env([Source(2, 0, 0, 1000)])
    check('clear_does_not_switch_channel', (e.clear(0, 0, 2)['clear_result'], e.channel), ('success', 1))
    check('cleared_source_has_no_signal', e.measure(0, 0, 2)['measure_result'], 'no_signal')
    check('clear_twice', e.clear(0, 0, 2)['clear_result'], 'no_target_in_range')
    check('empty_channel', e.measure(0, 0, 20)['measure_result'], 'no_signal')
    e = env([])
    for action, point, channel in [('measure', (300, 400), 1), ('measure', (300, 400), 2),
                                   ('clear', (300, 0), 3), ('measure', (300, 0), 2)]:
        getattr(e, action)(*point, channel)
    check('official_document_199_second_example', e.virtual_time_s, 199.0)
    check('official_document_final_channel', e.channel, 2)
    before = e.virtual_time_s
    e.exit()
    check('exit_does_not_advance_virtual_time', e.virtual_time_s, before)

    for point, expected in [((0, 0), 0.0), ((100, -100), 90.0),
                            ((200, 0), 180.0), ((100, 100), 270.0)]:
        e = env([Source(1, 100, 0, 1000)])
        check('bearing_'+str(int(expected)), e.measure(*point, 1)['svd_deg'], expected)
    e = LocalEnv([Source(1, 1000, 0, 1000)], seed=719, keep_log=False)
    e.enter()
    angle = e.measure(0, 0, 1)['svd_deg']
    e.measure(100, 0, 1)
    check('repeat_exact_coordinate_is_fixed', e.measure(0, 0, 1)['svd_deg'], angle)
    errors = [e.error(i*2.5, i*1.3, 1) for i in range(1000)]
    check('noise_within_one_degree', all(-1 <= x <= 1 for x in errors), True)

    # Use independently calculated angle/hemisphere membership rather than the
    # implementation's dot-product predicate for non-boundary bearing probes.
    for angle in [15, 37, 83, 121, 169, 201, 263, 319]:
        source_direction = math.radians(angle)
        for offset in [-91, -89, 0, 89, 91]:
            bearing = math.radians(angle+offset)
            point = (600*math.cos(bearing), 600*math.sin(bearing))
            e = env([Source(1, 0, 0, 1000, source_direction)])
            check('hemisphere_'+str(angle)+'_'+str(offset),
                  e.measure(*point, 1)['measure_result'],
                  'direction' if abs(offset) < 90 else 'no_signal')

    output=dict(checks=checks,passed=sum(c['passed'] for c in checks),total=len(checks))
    Path(args.out).write_text(json.dumps(output,indent=2))
    print(output['passed'], '/',output['total'])
    if not all(c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
