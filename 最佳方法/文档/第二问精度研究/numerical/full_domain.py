import json, math, os, time
from scan import worst, polar
start=time.time(); rows=[]
for length in range(25,1001,25):
    maxa=math.degrees(math.acos(length/2000))-1
    aa=[i for i in range(0,math.floor(maxa)+1)]+[maxa]
    rr=[worst(polar(length,a),nobs=160,narc=8) for a in aa]
    rows.extend(rr)
    win=min(rr,key=lambda r:r['worst_metric'])
    print(json.dumps({'length':length,'best_q':win['q'],'best_diameter':win['diameter']}),flush=True)
result={'elapsed_seconds':time.time()-start,'count':len(rows),'radial_grid':'25,50,...,1000 m','angular_grid':'0,1,...,floor(acos(b/2000)-1 deg), plus exact safety boundary','best':min(rows,key=lambda r:r['worst_metric']),'rows':rows}
with open(os.path.join(os.path.dirname(__file__),'full_domain_results.json'),'w') as f:json.dump(result,f,indent=2)
