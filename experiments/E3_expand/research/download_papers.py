"""Acquire author-hosted primary PDFs; never commit cached full texts."""
import pathlib,urllib.request,concurrent.futures,json,hashlib
ROOT=pathlib.Path(__file__).resolve().parent;CACHE=ROOT/'cache';CACHE.mkdir(exist_ok=True)
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
URLS={
 'iros2011':'https://josh.vanderhook.info/media/pdf/iros2011localization.pdf',
 'icra2012':'https://josh.vanderhook.info/media/pdf/icra2012bot.pdf',
 'iser2013':'https://josh.vanderhook.info/media/pdf/iser2013init.pdf',
 'jfr2014':'https://josh.vanderhook.info/media/pdf/JoshV_JFR_2013_Localization.pdf',
 'tro2015':'https://josh.vanderhook.info/media/pdf/tro2015cooploc.pdf',
 'wafr2020':'https://ksengin.github.io/papers/wafr2020active.pdf',
}
def one(item):
 key,url=item
 try:
  data=opener.open(url,timeout=40).read();assert data[:4]==b'%PDF'
  (CACHE/(key+'.pdf')).write_bytes(data)
  from pypdf import PdfReader
  pdf=PdfReader(CACHE/(key+'.pdf'))
  pages=[page.extract_text() for page in pdf.pages]
  (CACHE/(key+'.txt')).write_text('\n\n'.join(f'===== PAGE {i+1} =====\n'+text for i,text in enumerate(pages)))
  return dict(id=key,url=url,pdf_sha256=hashlib.sha256(data).hexdigest(),pages=len(pages),reading_status='downloaded and text extracted; not yet read')
 except Exception as e:return dict(id=key,url=url,error=repr(e))
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(one,URLS.items()))
 (ROOT/'download_manifest.json').write_text(json.dumps(rows,indent=2))
 print(json.dumps(rows,indent=2))
