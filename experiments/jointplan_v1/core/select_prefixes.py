"""P1 public-only boundary rule, fixed before geometry candidates are generated."""
import gzip,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    cases=json.loads((ROOT/'data/p0_exposed48.json').read_text())
    rows=json.loads((ROOT/'results/p0_disabled/case_metrics.json').read_text())
    byid={r['case_id']:r for r in rows};public=[];registry=[]
    for case in cases:
        row=byid[case['case_id']]
        data=json.loads(gzip.decompress((ROOT/'results/p0_disabled/runs'/(row['run_id']+'.json.gz')).read_bytes()))
        selected=[]
        for s in data['policy_diagnostics']['snapshots']:
            valid=len(s['stations'])>=4 and bool(s['source_tasks']) and not s['protected_plan_active']
            if not valid:continue
            if selected:
                a=selected[0]
                if len(s['cleared_channels'])<len(a['cleared_channels'])+3 and len(s['visited_station_ids'])<len(a['visited_station_ids'])+2:continue
            selected.append(s)
            if len(selected)==2:break
        refs=[]
        for s in selected:
            i=len(public);public.append(s);refs.append(dict(index=i,snapshot_hash=s['snapshot_hash'],history_version=s['history_version']))
        registry.append(dict(case_id=case['case_id'],mode=case['mode'],prefixes=refs,missing_prefixes=2-len(selected)))
    path=ROOT/'data/p1_public_snapshots.json';path.write_text(json.dumps(public,separators=(',',':'))+'\n')
    out=dict(rule='first public boundary with >=4 pending stations, nonempty source tasks, no protected plan; second such boundary after >=3 additional cleared channels OR >=2 additional visited stations',selector_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),public_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),worlds=len(cases),prefixes=len(public),registry=registry)
    (ROOT/'data/p1_prefix_registration.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='registry'}))
if __name__=='__main__':main()
