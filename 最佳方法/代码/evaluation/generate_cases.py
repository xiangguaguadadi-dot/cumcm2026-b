import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import random,math,json
from local_env import Source
def sources(seed, mode, scenario):
    r = random.Random(seed)
    n = 10 if scenario == 'count10' else 16 if scenario == 'count16' else r.randint(10, 16)
    channels = r.sample(range(1, 21), n)
    nd = 0 if mode == 3 else r.randint(1, n-1)
    phi = r.uniform(-math.pi, math.pi)
    center = (1450*math.cos(phi), 1450*math.sin(phi))
    out = []
    for i, ch in enumerate(channels):
        angle = r.uniform(-math.pi, math.pi)
        radius = 1800*math.sqrt(r.random())
        reach = r.uniform(1000, 1500)
        direction = r.uniform(-math.pi, math.pi) if i < nd else None
        x, y = radius*math.cos(angle), radius*math.sin(angle)
        if scenario == 'edge_mixed':
            radius = r.uniform(1700, 1800)
            x, y = radius*math.cos(angle), radius*math.sin(angle)
            reach = 1000
            direction = angle if i < nd else None
        elif scenario == 'cluster_offcenter':
            radius = 80*math.sqrt(r.random())
            x, y = center[0]+radius*math.cos(angle), center[1]+radius*math.sin(angle)
        elif scenario == 'cluster_origin':
            radius = 60*math.sqrt(r.random())
            x, y = radius*math.cos(angle), radius*math.sin(angle)
            reach = 1000
        elif scenario == 'min_radius':
            reach = 1000
        out.append(Source(ch, x, y, reach, direction))
    assert 10 <= len(out) <= 16
    assert all(math.hypot(s.x, s.y) <= 1800+1e-8 and 1000 <= s.radius <= 1500 for s in out)
    assert mode == 3 or 0 < sum(s.direction is not None for s in out) < len(out)
    return out

groups = [
    ('reference_assumed', 'random', 'uniform'),
    ('fixed_positive_bias', 'random', 'positive'),
    ('fixed_negative_bias', 'random', 'negative'),
    ('smooth_shared_field', 'random', 'smooth_shared'),
    ('cell50_shared_field', 'random', 'cell_50'),
    ('cell500_shared_field', 'random', 'cell_500'),
    ('edge_mixed_min_radius', 'edge_mixed', 'uniform'),
    ('offcenter_cluster', 'cluster_offcenter', 'uniform'),
    ('origin_cluster', 'cluster_origin', 'uniform'),
    ('minimum_radius', 'min_radius', 'uniform'),
    ('exactly10_sources', 'count10', 'uniform'),
    ('exactly16_sources', 'count16', 'uniform'),
]
from pathlib import Path
cases=[]
for mode in (3,4):
 for group,scenario,noise in groups:
  for index,seed in enumerate(range(5000,5100)):
   cases.append(dict(case_id=f"LOCAL-v1-q{mode}-{group}-{seed}",mode=mode,group=group,noise=noise,seed=seed,quick=index<5,sources=[vars(s) for s in sources(seed,mode,scenario)]))
Path(__file__).with_name('cases_v1.json').write_text(json.dumps(cases,ensure_ascii=False,separators=(',',':')))
