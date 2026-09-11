"""Follow verified author-list links; full texts remain in ignored cache."""
import pathlib,urllib.request,concurrent.futures,json,hashlib
from pypdf import PdfReader
ROOT=pathlib.Path(__file__).resolve().parent;CACHE=ROOT/'cache'
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
URLS={
'icra2013':'https://raaslab.org/pubs/tokekar2013asensor.pdf',
'isrr2015':'https://raaslab.org/pubs/dames2015detecting.pdf',
'isrr2017':'https://raaslab.org/pubs/dames2017detecting.pdf',
'ijrr2018':'https://raaslab.org/pubs/dames2018detecting.pdf',
'nonmyopic2016':'https://raaslab.org/pubs/zhang2016nonmyopic.pdf',
'fov2017':'https://raaslab.org/pubs/sung2017algorithm.pdf',
}
def one(kv):
 k,u=kv
 try:
  data=opener.open(u,timeout=40).read();assert data[:4]==b'%PDF'
  p=CACHE/(k+'.pdf');p.write_bytes(data);pages=[x.extract_text() for x in PdfReader(p).pages]
  (CACHE/(k+'.txt')).write_text('\n\n'.join(f'===== PAGE {i+1} =====\n'+x for i,x in enumerate(pages)))
  return dict(id=k,url=u,pdf_sha256=hashlib.sha256(data).hexdigest(),pages=len(pages),reading_status='downloaded; not yet read')
 except Exception as e:return dict(id=k,url=u,error=repr(e))
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(one,URLS.items()))
 (ROOT/'expansion_download_manifest.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
