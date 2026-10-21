"""Diagnostic official football report publisher discovery; produces no player assertions."""
import json,urllib.request,urllib.parse,html,re,hashlib
from html.parser import HTMLParser
from pathlib import Path
URLS={
 'sec':'https://www.secsports.com/fbreports',
 'b1g':'https://bigten.org/sports/2026/9/10/FB_Availability_Reports.aspx',
 'b1g_report':'https://app.hdintelligence.com/?source=B10&sport=Football&conf=B10&type=report',
 'b1g_archive':'https://app.hdintelligence.com/?source=B10&sport=Football&conf=B10&type=archive',
 'sec_archive':'https://www.secsports.com/fbreports-archive',
}
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag in ('iframe','a','script','link','embed'):
   target=d.get('src') or d.get('href')
   if target:self.links.append({'tag':tag,'target':html.unescape(target)})
def probe(output):
 out=Path(output);out.mkdir(parents=True,exist_ok=True)
 result={}
 for name,url in URLS.items():
  item={'url':url};result[name]=item
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; CFBResearch/0.1)','Accept':'text/html,*/*'})
   with urllib.request.urlopen(req,timeout=16) as r:
    raw=r.read(2_000_001);item['code']=r.status;item['final_url']=r.url;item['type']=r.headers.get('Content-Type');item['bytes']=len(raw)
    item['last_modified']=r.headers.get('Last-Modified');item['etag']=r.headers.get('ETag')
   if len(raw)>2_000_000:raise ValueError('oversize response')
   item['sha256']=hashlib.sha256(raw).hexdigest()
   body=raw.decode('utf-8','replace')
   (out/(name+'.html')).write_text(body)
   parsed=Links();parsed.feed(body)
   item['links']=[{'tag':x['tag'],'url':urllib.parse.urljoin(url,x['target'])} for x in parsed.links][:120]
   item['keywords']={k:len(re.findall(re.escape(k),body,re.I)) for k in ['report','pdf','iframe','hdintelligence','injury','availability','player','_next','window.__']}
  except Exception as e:item['error']=str(e)[:280]

 try:
  js_url="https://app.hdintelligence.com/assets/index-yMrVK3wN.js"
  req=urllib.request.Request(js_url,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=18) as r:
   raw=r.read(8_000_001)
  if len(raw)>8_000_000:raise ValueError("JS bundle over 8MB")
  js=raw.decode('utf-8','replace')
  (out/'hdintelligence_bundle.js').write_text(js)
  snippets=[]
  for match in re.finditer(r'(?i)public|availability|endpoint|report|archive|api/|axios|baseurl|fetch\\(',js):
   start=max(0,match.start()-120);end=min(len(js),match.end()+200)
   value=js[start:end]
   if value not in snippets:snippets.append(value)
   if len(snippets)>=220:break
  result["embedded_viewer_bundle"]={"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
        "snippets":snippets,"api_paths":list(dict.fromkeys(re.findall(r'["\\x27](/(?:api|v[12]|public)[^"\\x27\\\\\\s]{1,170})',js)))[:120],
        "url_strings":list(dict.fromkeys(re.findall(r'https?://[^"\\s\\x27<>]{5,180}',js)))[:100]}
 except Exception as exc:
  result["embedded_viewer_bundle"]={"error":str(exc)[:300]}
 (out/'report_probe.json').write_text(json.dumps(result,indent=2))
 print(json.dumps({k:{f:v for f,v in r.items() if f not in ('links',)} for k,r in result.items()},indent=2))
if __name__=='__main__':probe('data/availability_probe')
