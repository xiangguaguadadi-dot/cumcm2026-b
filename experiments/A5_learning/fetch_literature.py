"""Download primary papers; PDFs/text are a reproducible untracked cache."""
import subprocess, hashlib, json
from pathlib import Path
from pypdf import PdfReader
D=Path(__file__).resolve().parent/'literature_cache';D.mkdir(exist_ok=True)
items=[('ce','https://people.smp.uq.edu.au/DirkKroese/ps/CEopt.pdf'),('cma','https://arxiv.org/pdf/1604.00772'),('ars','https://arxiv.org/pdf/1803.07055'),('dagger','https://proceedings.mlr.press/v15/ross11a/ross11a.pdf'),('attention','https://arxiv.org/pdf/1803.08475'),('shield','https://arxiv.org/pdf/1708.08611'),('searn','https://arxiv.org/pdf/cs/0607120'),('rrig','https://arxiv.org/pdf/1307.0006'),('bo','https://arxiv.org/pdf/1807.02811'),('ppo','https://arxiv.org/pdf/1707.06347')]
log=[]
for key,url in items:
 p=D/(key+'.pdf');r=subprocess.run(['curl','--noproxy','*','-L','--max-time','50','-sS',url,'-o',str(p)],capture_output=True,text=True)
 rec=dict(id=key,url=url,returncode=r.returncode,error=r.stderr)
 try:
  reader=PdfReader(p); rec.update(pages=len(reader.pages),sha256=hashlib.sha256(p.read_bytes()).hexdigest());(D/(key+'.txt')).write_text('\n'.join(f'\n===== PAGE {i+1} =====\n'+(page.extract_text() or '') for i,page in enumerate(reader.pages)));print(key,rec['pages'],flush=True)
 except Exception as e: rec['error']+=str(e);print(key,rec['error'],flush=True)
 log.append(rec)
(D.parent/'literature_downloads.json').write_text(json.dumps(log,indent=2))
