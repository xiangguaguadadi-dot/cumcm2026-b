"""Reconstruct public polygons and verify pair lower witnesses; no env calls."""
import importlib.util,json,pathlib,math,heapq,hashlib,ast
HERE=pathlib.Path(__file__).resolve().parent
B=HERE.parent/'B_improved'
spec=importlib.util.spec_from_file_location('b_pure_geometry',B/'B1_minimax_costgate.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
G=M._G

def rebuild(trace,stop,ch,mode):
    poly=None;observations=[];neg=[];failed=[]
    def exclude(poly):
        if not poly:return poly
        for p,r in [(p,1000.-1e-6) for p in neg]+[(p,20.-1e-6) for p in failed]:
            if len(poly)>96:break
            new=G._geo_outside_disk_hull(poly,p,r)
            assert new
            if len(new)<=96:poly=new
        return poly
    for row in trace[:stop]:
        if row.get('channel')!=ch:continue
        p=(row['x'],row['y'])
        if row['action']=='measure':
            kind=row['result']
            if kind=='direction':
                deg=row['svd_deg'];observations.append((p,deg))
                poly=G._sp_add_bearing(poly if poly is not None else G._sp_initial_polygon(),p,deg)
                if mode==3:poly=G._geo_add_bearing(poly,p,deg)
            elif kind=='no_signal':neg.append(p)
            if mode==3 and kind in ('direction','no_signal'):poly=exclude(poly)
        elif row['action']=='clear' and row['result']!='success':
            failed.append(p)
            if mode==3:poly=exclude(poly)
    assert len(observations)==1
    return poly,observations,neg,failed

def diameter_pair(poly):
    best=0.;pair=None
    for i,p in enumerate(poly):
        for q in poly[i+1:]:
            d=math.dist(p,q)
            if d>best:best,pair=d,[p,q]
    return best,pair

def parent_pair_witness(poly,q):
    center,_=G._sp_enclosing_circle(poly)
    ref=math.atan2(center[1]-q[1],center[0]-q[0])
    angles=[math.remainder(math.atan2(p[1]-q[1],p[0]-q[0])-ref,2*math.pi) for p in poly]
    lo,hi=min(angles)-M._EPS,max(angles)+M._EPS
    assert (hi-lo)/2+M._EPS<math.pi/2-1e-5
    heap=[];serial=0;old_lower=0.;best_pair_bound=0.;witness=None
    def add(a,b):
        nonlocal serial,old_lower,best_pair_bound,witness
        mid=(a+b)/2
        upper=M._radius(M._wedge(poly,q,ref+mid,M._EPS+(b-a)/2))
        post=M._wedge(poly,q,ref+mid)
        value=M._radius(post);old_lower=max(old_lower,value)
        d,pair=diameter_pair(post)
        if d/2>best_pair_bound:
            best_pair_bound=d/2;witness={'bearing_rad':ref+mid,'pair':pair,'posterior_polygon':post,'pair_lower_radius_m':d/2}
        heapq.heappush(heap,(-upper,serial,a,b));serial+=1
    add(lo,hi)
    for _ in range(32):
        if -heap[0][0]<=old_lower+max(.25,.01*old_lower):break
        _,_,a,b=heapq.heappop(heap);mid=(a+b)/2;add(a,mid);add(mid,b)
    assert witness is not None
    return -heap[0][0],old_lower,witness

def inside(poly,q):
    cross=[(b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0]) for a,b in zip(poly,poly[1:]+poly[:1])]
    return all(x>=-1e-5 for x in cross) or all(x<=1e-5 for x in cross)

rows=[]
for variant in ('B1','B3'):
    path=B/'diagnostics'/(variant+'_first_per_group')/'public_diagnostics.json'
    data=json.loads(path.read_text())
    for case in data:
        for decision in case['decisions']:
            if not decision['changed'] or decision.get('executed_trace_index') is None:continue
            ch=decision['channel'];mode=case['mode']
            poly,obs,neg,failed=rebuild(case['public_trace'],decision['trace_index'],ch,mode)
            pu,pl,witness=parent_pair_witness(poly,decision['parent'])
            nu,nl=M._future_radius_bound(poly,decision['chosen'])
            differences=[pu-decision['parent_estimates']['worst_radius_upper_m'],pl-decision['parent_estimates']['worst_radius_lower_m'],nu-decision['chosen_estimates']['worst_radius_upper_m'],nl-decision['chosen_estimates']['worst_radius_lower_m']]
            assert max(abs(x) for x in differences)<1e-6,(variant,case['case_id'],ch,differences)
            q=decision['parent'];z=witness['bearing_rad']
            for p in witness['pair']:
                assert inside(poly,p)
                assert abs(math.remainder(math.atan2(p[1]-q[1],p[0]-q[0])-z,2*math.pi))<=M._EPS+1e-9
            gap=witness['pair_lower_radius_m']-nu
            event=case['public_trace'][decision['executed_trace_index']]
            assert event['action']=='measure' and event['channel']==ch
            assert math.dist((event['x'],event['y']),decision['chosen'])<1e-5
            rows.append({'variant':variant,'case_id':case['case_id'],'mode':mode,'channel':ch,'public_trace_index':decision['trace_index'],'executed_trace_index':decision['executed_trace_index'],'actual_second_result':event['result'],'prior_polygon':poly,'parent_point':decision['parent'],'chosen_point':decision['chosen'],'parent_enclosing_circle_lower_estimate':pl,'chosen_upper_radius_m':nu,'parent_pair_witness':witness,'pair_witness_minus_chosen_upper_m':gap,'pair_comparison_passes':gap>0,'recorded_bound_max_reconstruction_difference':max(abs(x) for x in differences),'scope':'retained-polygon angle-only posterior objective; no claim of physical-state feasibility after near/range/directional/exclusion constraints'})
assert len(rows)==75
variant_sources={};geometry_sources=[]
for variant,filename in [('B1','B1_minimax_costgate.py'),('B3','B3_local_refinement.py')]:
    source=B/filename;raw=source.read_text();tree=ast.parse(raw)
    parts=[ast.get_source_segment(raw,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_wedge','_radius','_future_radius_bound')]
    assert len(parts)==3;geometry='\n\n'.join(parts);geometry_sources.append(geometry)
    diagnostic=B/'diagnostics'/(variant+'_first_per_group')/'public_diagnostics.json'
    variant_sources[variant]={'candidate_path':str(source),'candidate_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'public_diagnostics_path':str(diagnostic),'public_diagnostics_sha256':hashlib.sha256(diagnostic.read_bytes()).hexdigest(),'shared_geometry_functions_sha256':hashlib.sha256(geometry.encode()).hexdigest()}
assert geometry_sources[0]==geometry_sources[1]
result={'scope':'pure public-trace geometry reconstruction; no Solver.run, LocalEnv or environment interface calls; not interval arithmetic','rows':rows,'count':len(rows),'pair_comparisons_passed':sum(r['pair_comparison_passes'] for r in rows),'min_pair_gap_m':min(r['pair_witness_minus_chosen_upper_m'] for r in rows),'max_pair_gap_m':max(r['pair_witness_minus_chosen_upper_m'] for r in rows),'max_bound_reconstruction_difference':max(r['recorded_bound_max_reconstruction_difference'] for r in rows),'uses_mec_estimate_as_lower':False,'geometry_evaluator_sha256':hashlib.sha256((B/'B1_minimax_costgate.py').read_bytes()).hexdigest(),'geometry_evaluator_note':'B1 module supplies the shared pure geometry functions; AST-extracted _wedge, _radius and _future_radius_bound source matches B3 exactly; per-variant candidate/diagnostic hashes are separate.','variant_sources':variant_sources}
(HERE/'B_geometry_pair_witnesses.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
