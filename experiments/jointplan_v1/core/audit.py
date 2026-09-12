"""Independent saved-record audit. Does not import or execute candidate/environment."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import zipfile


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def normalize(value):
    if isinstance(value,dict):return {k:normalize(v) for k,v in value.items() if k not in ('real_timestamp_ms','remaining_real_duration_s') and not k.endswith('_cpu_s')}
    if isinstance(value,list):return [normalize(v) for v in value]
    return value

def audit_batch(batch):
    batch=Path(batch);reg=load(batch/'registration.json');summary=load(batch/'summary.json')
    cases={x['case_id']:x for x in load(reg['cases'])}; rows=load(batch/'case_metrics.json')
    assert len(rows)==len(cases)==reg['cases_count']
    assert {x['case_id'] for x in rows}==set(cases)
    assert len({x['run_id'] for x in rows})==len(rows)
    assert sha(batch/'frozen_inputs.zip')==reg['frozen_archive_sha256']
    with zipfile.ZipFile(batch/'frozen_inputs.zip') as z:
        assert z.testzip() is None
        contents={hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}
        assert set(reg['source_files'].values())<=contents
    payloads={};totals=Counter()
    for row in rows:
        rid=row['run_id'];case=cases[row['case_id']]
        data=json.loads(gzip.decompress((batch/'runs'/(rid+'.json.gz')).read_bytes()))
        assert data['row']==row
        journal=[json.loads(line) for line in gzip.decompress((batch/'runs'/(rid+'.journal.jsonl.gz')).read_bytes()).decode().splitlines()]
        assert len(journal)%2==0
        counts=Counter(attempts=0,accepted=0,rejected=0,unknown=0,known_error=0)
        pos=(0.,0.);channel=1;virtual_us=0;dist=0.;measures=switches=clears=0;cleared=set();entered=exited=False;traces=[]
        sources={s['channel']:s for s in case['sources']}
        for i in range(0,len(journal),2):
            request,response=journal[i:i+2]
            assert request['event']=='attempt' and response['event']=='outcome'
            assert request['seq']==response['seq']==i//2
            counts['attempts']+=1;counts[response['category']]+=1
            traces.append([normalize(request),normalize(response)])
            if response['category']!='accepted':continue
            args=request['args'];action=request['action'];r=response['response'];assert r['accepted'] is True
            if action=='enter':assert not entered;entered=True;cost=0.
            elif action=='exit':assert entered and not exited;exited=True;cost=0.
            else:
                assert entered and not exited
                x,y,ch=args;assert all(type(v) in (float,int) and math.isfinite(v) for v in args)
                assert int(ch)==ch and 1<=ch<=20
                d=math.hypot(x-pos[0],y-pos[1]);dist+=d;pos=(x,y);cost=d/5
                if action=='measure':
                    measures+=1;switches+=int(ch!=channel);cost+=5+(ch!=channel);channel=ch
                else:
                    assert action=='clear';clears+=1;cost+=3
                    s=sources.get(ch);should=bool(s and ch not in cleared and math.hypot(x-s['x'],y-s['y'])<=20+1e-10)
                    assert (r['clear_result']=='success')==should
                    if should:cleared.add(ch);cost+=2
            virtual_us+=math.floor(cost*1e6+.5)
            assert round(r['virtual_time_s']*1e6)==virtual_us
        assert dict(counts)==data['calls']
        assert row['source_count']==len(sources) and row['cleared_count']==len(cleared)
        assert row['measures']==measures and row['switches']==switches and row['clear_attempts']==clears
        assert math.isclose(row['distance_m'],dist,abs_tol=1e-7)
        assert round(row['total_virtual_time_s']*1e6)==virtual_us
        assert row['average_clear_time_s']==(virtual_us/1e6/len(cleared) if cleared else None)
        success=exited and len(cleared)==len(sources) and row['error'] is None
        assert row['complete']==success
        assert row['policy_sha256']==reg['source_files'][reg['candidate']]
        assert row['world_sha256']==hashlib.sha256(json.dumps(case,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
        totals.update(counts);payloads[row['case_id']]=dict(row=row,traces=traces,data=data)
    assert summary['all_complete']==all(r['complete'] for r in rows)
    modes={str(q):dict(worlds=len(v:=[r for r in rows if r['mode']==q]),sources=sum(r['source_count'] for r in v),complete=sum(r['complete'] for r in v),mean_seconds_per_source=statistics.mean(r['average_clear_time_s'] for r in v) if all(r['complete'] for r in v) else None) for q in sorted({r['mode'] for r in rows})}
    return dict(passed=True,batch=str(batch),runs=len(rows),calls=dict(totals),modes=modes),payloads

def paired(a,b,exact=False):
    ra,pa=a;rb,pb=b;assert set(pa)==set(pb)
    modes={};snapshots=0
    for cid in pa:
        left,right=pa[cid],pb[cid]
        assert left['row']['world_sha256']==right['row']['world_sha256']
        if exact:
            assert left['traces']==right['traces'],('trace mismatch',cid)
            assert normalize(left['data']['semantic_state'])==normalize(right['data']['semantic_state']),('state mismatch',cid)
            snaps=right['data'].get('policy_diagnostics',{}).get('snapshots',[])
            assert snaps,('missing public snapshots',cid)
            snapshots+=len(snaps)
    for q in sorted({v['row']['mode'] for v in pa.values()}):
        ids=[cid for cid in pa if pa[cid]['row']['mode']==q]
        complete=all(pa[c]['row']['complete'] and pb[c]['row']['complete'] for c in ids)
        deltas=[pb[c]['row']['average_clear_time_s']-pa[c]['row']['average_clear_time_s'] for c in ids] if complete else []
        modes[str(q)]=dict(worlds=len(ids),all_complete=complete,mean_delta_seconds_per_source=statistics.mean(deltas) if deltas else None,faster=sum(x<0 for x in deltas),same=sum(x==0 for x in deltas),slower=sum(x>0 for x in deltas),worst_regression_seconds=max(deltas) if deltas else None)
    return dict(passed=True,exact=exact,public_snapshots=snapshots,modes=modes)

def main():
    p=argparse.ArgumentParser();p.add_argument('batches',nargs='+',type=Path);p.add_argument('--exact',action='store_true');p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    audited=[audit_batch(b) for b in args.batches]
    result=dict(auditor_sha256=sha(__file__),batches=[a[0] for a in audited])
    if len(audited)==2:result['paired']=paired(*audited,exact=args.exact)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
