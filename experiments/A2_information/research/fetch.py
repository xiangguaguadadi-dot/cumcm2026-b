import subprocess,pathlib,json,hashlib,concurrent.futures
from pypdf import PdfReader
root=pathlib.Path(__file__).resolve().parent
ids=['1908.00380','2310.15846','1804.02573','2603.04867','2405.02605','1705.07834','2605.11116','1703.09924','2009.07308']
def fetch(i):
 p=root/(i+'.pdf'); u='https://arxiv.org/pdf/'+i
 s=subprocess.run(['curl','--noproxy','*','-fLsS','--max-time','40',u,'-o',str(p)],capture_output=True,text=True)
 if s.returncode:return {'id':i,'error':s.stderr}
 reader=PdfReader(p); text='\n'.join('\n=== PAGE %d ===\n%s'%(k+1,z.extract_text()) for k,z in enumerate(reader.pages))
 (root/(i+'.txt')).write_text(text)
 return {'id':i,'url':u,'pages':len(reader.pages),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:r=list(pool.map(fetch,ids))
(root/'downloads.json').write_text(json.dumps(r,indent=2))
print(json.dumps(r,indent=2))
