"""Standard-library paths and immutable artifact helpers for this round only."""
from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
RL=ROOT.parent
REPO=RL.parents[2]
BASE=RL/'implementation'
WORLD_SOURCE=REPO/'experiments/20260911_rl_execution/data/worlds.py'
WORLD_PIN='f595623edd01fbcaeefd64a05bf3905f13deb25f9508d2f813e94715a5509f80'
SEEDS=[912101,912102,912103]
ROLES={'fit':24,'fit_val':12,'calibration':24,'development':120}
CARRY_IN={'business_calls':197456,'executions_started':1696}
LIMITS=dict(business_calls=1000000,executions=3000,run_call_reserve=15846,
    campaign_wall_s=21600,raw_bytes=8*1024**3,rss_bytes=16*1024**3,
    phase_calls={'labels':500000,'calibration':150000,'development':300000,'compatibility':50000},
    compatibility_executions=24)

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False)

def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path):
    path=Path(path)
    if path.suffix=='.gz':
        with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)
    return json.loads(path.read_text())

def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.pending')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    temporary.replace(path)

def save_new(path,value):
    path=Path(path)
    if path.exists():raise FileExistsError('Immutable artifact exists: '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.suffix=='.gz':
        with gzip.open(path,'xt',encoding='utf-8') as f:
            json.dump(value,f,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    else:atomic_json(path,value)
