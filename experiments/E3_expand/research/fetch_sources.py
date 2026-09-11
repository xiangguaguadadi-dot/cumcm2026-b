"""Read-only public source acquisition. Full-text cache is gitignored."""
import concurrent.futures,json,urllib.request,urllib.parse,pathlib,hashlib,time
ROOT=pathlib.Path(__file__).resolve().parent
CACHE=ROOT/'cache';CACHE.mkdir(exist_ok=True)
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
queries={
 'IROS2011':'Active Target Localization for Bearing Based Robotic Telemetry',
 'ICRA2012':'Cautious Greedy Strategy for Bearing-based Active Localization Experiments and Theoretical Analysis',
 'ICRA2013':'Sensor Placement and Selection for Bearing Sensors with Bounded Uncertainty',
 'ISER2013':'Local-Search Strategy for Active Localization of Multiple Invasive Fish',
 'JFR2014':'Cautious Greedy Strategy for Bearing-only Active Localization Analysis and Field Experiments',
 'TRO2015':'Algorithms for Cooperative Active Localization of Static Targets With Mobile Bearing Sensors Under Communication Constraints',
 'ISRR2015':'Detecting Localizing and Tracking an Unknown Number of Moving Targets',
 'ARXIV2020':'Active Localization of Multiple Targets using Noisy Relative Measurements',
}
def fetch_query(item):
 key,title=item
 url='https://api.crossref.org/works?'+urllib.parse.urlencode({'query.title':title,'rows':3})
 try:
  raw=opener.open(urllib.request.Request(url,headers={'User-Agent':'AcademicLiteratureResearch/1.0'}),timeout=40).read()
  (CACHE/(key+'_crossref.json')).write_bytes(raw)
  d=json.loads(raw)
  rows=[{k:r[k] for k in ['title','author','DOI','published','published-print','published-online','container-title','event','URL','link','abstract'] if k in r} for r in d['message']['items']]
  return dict(id=key,query=title,url=url,sha256=hashlib.sha256(raw).hexdigest(),candidates=rows)
 except Exception as e:return dict(id=key,query=title,url=url,error=repr(e))
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  out=list(pool.map(fetch_query,queries.items()))
 (ROOT/'identity_discovery.json').write_text(json.dumps(out,indent=2,ensure_ascii=False))
 for r in out:
  print(r['id'],r.get('error',''))
  for x in r.get('candidates',[]): print(x.get('title'),x.get('DOI'),x.get('published'),x.get('container-title'))
