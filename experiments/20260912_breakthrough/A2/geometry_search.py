"""Bounded alternative ring-count search; sample passes are NOT certificates."""
import argparse,json,math,time
from pathlib import Path
HERE=Path(__file__).resolve().parent

def ring(n,r,phase=0):
    return [(round(r*math.cos(2*math.pi*k/n+phase),6),round(r*math.sin(2*math.pi*k/n+phase),6)) for k in range(n)]

def covered(p,sites):
    angles=[]
    for q in sites:
        dx=q[0]-p[0];dy=q[1]-p[1];d2=dx*dx+dy*dy
        if d2<1e-12:return True
        if d2<=1000**2+1e-7:angles.append(math.atan2(dy,dx))
    if len(angles)<2:return False
    angles.sort();maxgap=max(b-a for a,b in zip(angles,angles[1:]))
    maxgap=max(maxgap,angles[0]+2*math.pi-angles[-1])
    return maxgap<=math.pi+1e-10

def probe(sites,radial=46,angular=360,max_bad=12):
    bad=[];seen=0
    # Outer region first, where fewer external sites most often fail.
    for i in reversed(range(radial)):
        # Strictly inside the target disk; avoid floating boundary artifacts.
        r=1799.999999*i/(radial-1)
        for j in range(angular):
            angle=2*math.pi*j/angular;p=(r*math.cos(angle),r*math.sin(angle));seen+=1
            if not covered(p,sites):
                bad.append(p)
                if len(bad)>=max_bad:return dict(sampled=seen,failures=bad,passed=False)
    return dict(sampled=seen,failures=bad,passed=not bad)

def main():
    p=argparse.ArgumentParser();p.add_argument('--total',type=int,default=20);p.add_argument('--out',required=True);a=p.parse_args()
    out=HERE/'results'/a.out;out.mkdir(exist_ok=False);start=time.perf_counter();records=[]
    # Exact bounded list, never a task-data optimization or online source input.
    for outer_n in [9,10,11,12,13]:
        inner_n=a.total-1-outer_n
        for inner_r in [950.,980.,999.]:
            for extra in [.2,10.,30.,60.]:
                outer_r=1800/math.cos(math.pi/outer_n)+extra
                for phase_index in range(3):
                    phase=math.pi*phase_index/(3*outer_n)
                    sites=[(0.,0.)]+ring(inner_n,inner_r)+ring(outer_n,outer_r,phase)
                    result=probe(sites)
                    records.append(dict(total=a.total,inner_n=inner_n,outer_n=outer_n,inner_r=inner_r,outer_r=outer_r,phase=phase,
                        sites=sites,**result))
                    if result['passed']:print('SAMPLE_PASS',len(records)-1,inner_n,outer_n,inner_r,outer_r,phase,flush=True)
        print('finished outer count',outer_n,'tested',len(records),'sample_pass',sum(r['passed'] for r in records),flush=True)
    (out/'records.json').write_text(json.dumps(records,indent=2)+'\n')
    summary=dict(configurations=len(records),sample_passes=[i for i,r in enumerate(records) if r['passed']],wall_s=time.perf_counter()-start,
        note='Only counterexample search: zero uncovered samples is not continuous coverage')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary)

if __name__=='__main__':main()
