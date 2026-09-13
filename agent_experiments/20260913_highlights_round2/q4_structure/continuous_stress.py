"""Constructed stress test for the widened continuous heading certificate."""
import argparse, json, math, random
from pathlib import Path
from run_experiment import heading_certificate

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--cases",type=int,default=100000);ap.add_argument("--out",required=True);a=ap.parse_args()
    rng=random.Random(20260913); failures=[]; widths=[]; boundary=0
    for i in range(a.cases):
        sr=1800*math.sqrt(rng.random());sa=rng.uniform(-math.pi,math.pi);sx,sy=sr*math.cos(sa),sr*math.sin(sa)
        heading=rng.uniform(-math.pi,math.pi);er=20*math.sqrt(rng.random());ea=rng.uniform(-math.pi,math.pi)
        clear=(sx+er*math.cos(ea),sy+er*math.sin(ea));trace=[]
        for j in range(rng.randint(2,8)):
            # Include exact half-plane boundary observations regularly.
            offset=(math.pi/2 if (i+j)%17==0 else rng.uniform(-math.pi/2,math.pi/2))
            boundary += int(abs(abs(offset)-math.pi/2)<1e-14)
            rr=rng.uniform(20.0001,1500);p=(sx+rr*math.cos(heading+offset),sy+rr*math.sin(heading+offset))
            trace.append({"action":"measure","channel":1,"result":"direction","x":p[0],"y":p[1]})
        trace.append({"action":"clear","channel":1,"result":"success","x":clear[0],"y":clear[1]})
        h=heading_certificate({"channel":1,"direction":heading},trace);widths.append(h["feasible_width_deg"])
        if not h["true_heading_retained"]: failures.append({"i":i,"source":[sx,sy],"heading":heading,"clear":clear,"result":h})
    # Three distant positive sites 120 degrees apart are incompatible with any
    # directional half-plane, but are valid for an omni source.
    omni_pass=0
    for i in range(1000):
        rot=2*math.pi*i/1000;trace=[]
        for k in range(3):
            ang=rot+2*math.pi*k/3;trace.append({"action":"measure","channel":1,"result":"direction","x":1200*math.cos(ang),"y":1200*math.sin(ang)})
        trace.append({"action":"clear","channel":1,"result":"success","x":0.,"y":0.})
        omni_pass += heading_certificate({"channel":1,"direction":None},trace)["omni_certificate"]
    result={"status":"pass" if not failures and omni_pass==1000 else "fail","directional_cases":a.cases,
      "boundary_positive_sites":boundary,"directional_exclusions":len(failures),"first_failures":failures[:3],
      "median_width_deg":sorted(widths)[len(widths)//2],"constructed_omni_cases":1000,"omni_certified":omni_pass,
      "seed":20260913,"evidence":"constructed analytic stress; not closed-loop or official"}
    Path(a.out).write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result))
if __name__=="__main__":main()
