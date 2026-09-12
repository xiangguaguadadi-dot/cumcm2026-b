"""Independent saved-row verification; executes no solver or simulator."""
from __future__ import annotations
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj

def source_audit(candidate,baseline):
    raw=candidate.read_text(); parent=baseline.read_text()
    if raw.startswith(parent+'\n\n'):
        patch=raw[len(parent):]; kind='exact parent prefix'
    else:
        tree=ast.parse(raw); embedded=[]; end=0
        for n in tree.body:
            if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='exec':
                for t in ast.walk(n):
                    if isinstance(t,ast.Constant) and isinstance(t.value,str) and t.value==parent:
                        embedded.append(t.value);end=n.end_lineno
        assert len(embedded)==1, 'Parent not embedded exactly once: '+str(candidate)
        patch='\n'.join(raw.splitlines()[end:]); kind='exact parent literal'
    tree=ast.parse(patch)
    protected={'measure','clear','run','cover_polygon','rescue_bearing','scan_station','refine_no_signal','_accept','_virtual_fallback'}
    forbidden={'open','eval','exec','__import__','getattr','setattr','globals','locals'}
    methods=[]; suspicious=[]
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            methods.append(n.name)
            assert n.name not in protected, 'Protected method overridden: '+n.name
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in forbidden:
            suspicious.append((n.lineno,n.func.id))
    assert not suspicious, suspicious
    return dict(candidate_sha256=sha(candidate),parent_sha256=sha(baseline),embedding=kind,
                patch_sha256=hashlib.sha256(patch.encode()).hexdigest(),declared_functions=methods,
                no_protected_method_overrides=True,note='Structural check plus human source review; AST scanning is not a security proof.')

def main():
    reg=read(HERE/'REGISTRATION.json')
    for p,h in reg['files'].items():assert sha(ROOT/p)==h
    helper_path=ROOT/'experiments/parallel_v2_coordinator/audit_pair.py'
    helper=load('independent_previous_pair_audit',helper_path)
    cases_all=read(ROOT/'experiments/20260911_stage4/exposed_cases.json')
    cases={c['case_id']:c for c in cases_all}
    refs_all=read(ROOT/'experiments/parallel_v2_coordinator/fusion_r5_exposed/case_metrics.json')
    refs={r['case_id']:r for r in refs_all}
    output=[];sources={};actual_runs=0;actual_requests=0
    for summary_path in sorted(HERE.glob('*/results/*/summary.json')):
        summary=read(summary_path);directory=summary_path.parent
        registration=read(directory/'execution_registration.json')
        # Preserve original absolute execution paths in registrations, but
        # resolve archived candidates relative to this checkout for replay.
        candidate=HERE/directory.relative_to(HERE).parts[0]/Path(registration['candidate']).name
        assert sha(candidate)==summary['candidate_sha256']==registration['candidate_sha256']
        assert summary['baseline_sha256']==reg['baseline_sha256']
        assert summary['registration_sha256']==sha(HERE/'REGISTRATION.json')
        assert summary['runner_sha256']==sha(HERE/'evaluate_transfer.py')
        rows=read(directory/'case_metrics.json');ids=[r['case_id'] for r in rows]
        assert ids==registration['case_ids'] and len(ids)==summary['paired_cases']
        chosen=[cases[cid] for cid in ids];reference=[refs[cid] for cid in ids]
        independent=helper.compare(rows,reference,chosen,bootstrap_repeats=2000)
        assert independent['all_complete']==summary['all_complete']
        for r in summary['comparisons']:
            other=next(s for s in independent['comparisons'] if s['mode']==r['mode'] and s['suite']==r['batch'] and s['group']==r['group'])
            assert other['valid_comparison']==r['valid_comparison']
            if r['valid_comparison']:
                for key in ('candidate_mean','baseline_mean','delta','improvement_pct'):
                    assert abs(other[key]-r[key])<1e-9,(directory,key)
        executed=[json.loads(line) for line in (directory/'executed_rows.jsonl').read_text().splitlines()]
        assert len(executed)==summary['actual_runs']
        ei={r['case_id']:r for r in executed}
        assert len(ei)==len(executed)
        assert all(r==ei[r['case_id']] for r in rows if r['case_id'] in ei)
        if registration['reused']:
            prev=directory.parent/Path(registration['reused']['path']).name/'case_metrics.json'
            assert sha(prev)==registration['reused']['rows_sha256']
            pi={r['case_id']:r for r in read(prev)}
            assert set(pi).isdisjoint(ei) and set(pi)|set(ei)==set(ids)
            assert all(r==pi[r['case_id']] for r in rows if r['case_id'] in pi)
        else:assert set(ei)==set(ids)
        requests=sum(r.get('requests',0) or 0 for r in executed)
        assert requests==summary['actual_requests']
        actual_runs+=len(executed);actual_requests+=requests
        sourcekey=str(candidate.relative_to(HERE))
        if sourcekey not in sources:sources[sourcekey]=source_audit(candidate,HERE/'baseline.py')
        output.append(dict(result=str(directory.relative_to(HERE)),suite=summary['suite'],candidate_sha256=summary['candidate_sha256'],
                           actual_runs=len(executed),actual_requests=requests,rows_sha256=sha(directory/'case_metrics.json'),
                           independent_audit=independent))
    result=dict(status='passed',audit_script_sha256=sha(__file__),pair_helper_sha256=sha(helper_path),
                solver_runs_executed_by_this_audit=0,completed_experiment_runs=actual_runs,
                completed_experiment_requests=actual_requests,results=output,sources=sources,
                pending_experiment_results=[str(p.parent.relative_to(HERE)) for p in HERE.glob('*/results/*/execution_registration.json') if not (p.parent/'summary.json').exists()],
                note='Counts above exclude baseline reproduction, synthetic checks and separate diagnostic reruns; these are separately inventoried in the final report.')
    (HERE/'INDEPENDENT_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','completed_experiment_runs','completed_experiment_requests','pending_experiment_results')},ensure_ascii=False))

if __name__=='__main__':main()
