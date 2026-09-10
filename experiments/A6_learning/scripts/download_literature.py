"""Re-download source PDFs recorded in literature.json; do not imply full reading."""
import hashlib,json,subprocess
from pathlib import Path
base=Path(__file__).resolve().parents[1];cache=base/'literature_cache';cache.mkdir(exist_ok=True)
for p in json.loads((base/'literature.json').read_text())['papers']:
 file=cache/(p['id']+'.pdf')
 subprocess.run(['curl','--noproxy','*','-L','--fail','--max-time','90','-o',str(file),p['original_url']],check=True)
 sha=hashlib.sha256(file.read_bytes()).hexdigest()
 print(p['id'],sha,'match' if sha==p['pdf_sha256'] else 'VERSION OR CONTENT CHANGED')
