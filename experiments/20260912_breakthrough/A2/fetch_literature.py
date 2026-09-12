"""Archive accessed primary-source HTML and readable text; no task actions."""
import concurrent.futures,hashlib,html,json,re,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
PAPERS={'adaptive_submodularity':'1003.3967v5','d_opt_reweight':'2605.11116v1',
 'guaranteed_ipp':'2602.05198v3','ia_tigris':'2502.15961v3',
 'circle_tsp':'2003.06712','lawn_mowing':'2211.05891'}

def fetch(pair):
    name,aid=pair;folder=HERE/'literature/raw';folder.mkdir(parents=True,exist_ok=True)
    rows=[]
    for kind in ['abs','html']:
        url='https://arxiv.org/'+kind+'/'+aid
        result=subprocess.run(['curl','--noproxy','*','-L','--max-time','30','-sS',url],capture_output=True)
        content=result.stdout.decode(errors='replace');target=folder/(name+'_'+kind+'.html')
        target.write_text(content)
        text=re.sub(r'<(script|style)\b.*?</\1>','',content,flags=re.S)
        text=re.sub(r'<math\b.*?</math>',lambda m:' '+html.unescape(re.search(r'alttext="([^"]*)',m[0])[1])+' ' if re.search(r'alttext="([^"]*)',m[0]) else '',text,flags=re.S)
        text=re.sub(r'</(?:p|div|section|h[1-6]|li|tr)>','\n',text)
        text=html.unescape(re.sub(r'<[^>]*>',' ',text))
        text='\n'.join(re.sub(r'\s+',' ',line).strip() for line in text.splitlines() if line.strip())
        (folder/(name+'_'+kind+'.txt')).write_text(text+'\n')
        rows.append(dict(url=url,file=str(target.relative_to(HERE)),sha256=hashlib.sha256(result.stdout).hexdigest(),
            returncode=result.returncode,error=result.stderr.decode(errors='replace'),bytes=len(result.stdout),
            paper_html=(kind=='html' and 'ltx_title_section' in content)))
    return name,rows

if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:result=dict(pool.map(fetch,PAPERS.items()))
    (HERE/'literature/fetch_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:[(x['returncode'],x['bytes'],x['paper_html']) for x in v] for k,v in result.items()}))
