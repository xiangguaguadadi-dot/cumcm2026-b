"""Re-download primary PDFs into local ignored cache; no policy deployment dependency."""
import hashlib,json,pathlib,subprocess
p=pathlib.Path(__file__).resolve().parent
for entry in json.loads((p/'downloads.json').read_text()):
 target=p/(entry['id']+'.pdf')
 subprocess.run(['curl','--noproxy','*','-L','--fail','--max-time','60',entry['url'],'-o',str(target)],check=True)
 actual=hashlib.sha256(target.read_bytes()).hexdigest()
 print(entry['id'],'verified' if actual==entry['sha256'] else 'HASH CHANGED; inspect upstream revision')
