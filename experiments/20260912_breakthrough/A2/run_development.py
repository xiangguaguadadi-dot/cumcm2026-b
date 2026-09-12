"""A2 evaluator only: legal-world generation and full raw results, never solver input."""
import argparse,collections,importlib.util,json,math,statistics,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('e2_eval_helper',ROOT/'experiments/E2_refine/develop.py')
D=importlib.util.module_from_spec(spec);spec.loader.exec_module(D)
C7=ROOT/'experiments/20260911_stage4/combination/geometry_fusions/C7_both.py'

def save(p,value):
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def diagnose(details):
    counts=collections.Counter();secs=collections.Counter()
    for detail in details:
        prev=(0.,0.);pt=0.;known=set()
        for row in detail['trace']:
            context=row['context'];p=(row['x'],row['y'])
            tag=('opportunity' if 'share_observations' in context else
                'optical' if 'cover_polygon' in context else
                'rescue' if 'rescue_bearing' in context else
                ('station_known' if row['channel'] in known else 'station_unknown') if 'scan_station' in context else 'service')
            counts[f"{tag}/{row['action']}/{row['result']}"]+=1
            movement=math.dist(prev,p)/5
            secs[tag+'/movement']+=movement
            secs[tag+'/nonmovement']+=row['virtual_time_s']-pt-movement
            if row['action']=='measure' and row['result'] in ('direction','near'):known.add(row['channel'])
            prev=p;pt=row['virtual_time_s']
    return dict(traces=len(details),action_counts=counts,virtual_seconds=secs)

def main():
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--candidate',nargs='*',default=[])
    p.add_argument('--cases');p.add_argument('--baseline');p.add_argument('--seed',type=int,default=62000000)
    p.add_argument('--per-group',type=int,default=8);p.add_argument('--config',default='{}')
    args=p.parse_args();out=HERE/'results'/args.batch;out.mkdir(parents=True,exist_ok=False)
    cases=(json.loads(Path(args.cases).read_text()) if args.cases else
        [D.make_case(args.seed+g*args.per_group+i,4,group,scenario,noise)
        for g,(group,scenario,noise) in enumerate(D.GROUPS) for i in range(args.per_group)])
    save(out/'cases.json',cases);traces={c['case_id'] for i,c in enumerate(cases) if i%args.per_group==0}
    variants=[C7]+[Path(s).resolve() for s in args.candidate];baseline=None;summary={}
    for v,source in enumerate(variants):
        name='C7' if v==0 else source.stem;details=[];start=time.perf_counter()
        if v==0 and args.baseline:rows=json.loads(Path(args.baseline).read_text());runs=0
        else:
            module=D.load(source);rows=[]
            for i,c in enumerate(cases):
                row,detail=D.run_case(module,c,c['case_id'] in traces,config=json.loads(args.config) if v else None)
                rows.append(row)
                if detail:
                    details.append(detail);save(out/(name+'__'+c['case_id']+'_trace.json'),detail)
                if (i+1)%24==0:print(name,i+1,len(cases),flush=True)
            runs=len(rows)
        save(out/(name+'_rows.json'),rows)
        if v==0:baseline=rows
        summary[name]=dict(source=str(source),sha256=D.sha(source),runs=runs,wall_s=time.perf_counter()-start,
            comparisons=D.comparisons(rows,baseline),diagnosis=diagnose(details))
        save(out/'summary.json',summary)
        print(name,[r for r in summary[name]['comparisons'] if r['group']=='ALL'],flush=True)

if __name__=='__main__':main()
