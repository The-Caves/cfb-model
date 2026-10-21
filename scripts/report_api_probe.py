"""Probe HDI public report endpoints used by official conference embeds.

Only calls public, unauthenticated endpoints explicitly referenced in official
viewer frontend. Does not use admin APIs or any embedded private keys.
"""
import datetime as dt,json,urllib.request,urllib.error,hashlib
from pathlib import Path

ROOT="https://app.hdintelligence.com"
CONFS={"SEC":"SEC","B10":"B10"}
ENDPOINTS=("/api/public-load","/api/get-publish-public","/api/get-archive-public")
def call(path,body):
    payload=json.dumps(body).encode()
    req=urllib.request.Request(ROOT+path,data=payload,method="POST",headers={
        "Content-Type":"application/json","Accept":"application/json",
        "Origin":ROOT,"User-Agent":"CFB-Research-PublicReport/0.1"})
    try:
        with urllib.request.urlopen(req,timeout=20) as resp:
            raw=resp.read(25_000_001)
            status=resp.status
        if len(raw)>25_000_000:raise ValueError("Response too large")
        try:return {"status":status,"data":json.loads(raw),"sha256":hashlib.sha256(raw).hexdigest()}
        except json.JSONDecodeError:return {"status":status,"non_json_preview":raw[:100].decode(errors="replace")}
    except urllib.error.HTTPError as e:
        return {"status":e.code,"http_error_preview":e.read(200).decode(errors="replace")}
    except Exception as e:return {"error":str(e)[:250]}
def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    report={"captured_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"results":{}}
    for conf,source in CONFS.items():
        report["results"][conf]={}
        for path in ENDPOINTS:
            body={"conference_param":conf,"sport_param":"Football","type_param":"report",
                  "referrer":"", "source":source} if path=="/api/public-load" else {
                  "sport":"Football","organization":source,"conference":conf}
            result=call(path,body)
            name=conf+"_"+path.split("/")[-1]
            # Keep diagnostics compact and avoid storing embedded logos or image blobs.
            safe=json.loads(json.dumps(result))
            if isinstance(safe.get("data"),dict):
                for value in safe["data"].values():
                    if not isinstance(value,dict):continue
                    for image_key in list(value):
                        if "image" in image_key.lower() or "logo" in image_key.lower():
                            value[image_key]="[omitted image]"
                    for game in value.get("games",[]):
                        for row in game.get("rows",[]):
                            for image_key in list(row):
                                if "image" in image_key.lower() or "logo" in image_key.lower():
                                    row[image_key]="[omitted image]"
                        if "teamImage" in game:game["teamImage"]="[omitted image]"
            (out/(name+".json")).write_text(json.dumps(safe,indent=2))
            data=result.get("data")
            summary={"status":result.get("status"),"error":result.get("error"),
              "sha256":result.get("sha256"),"type":type(data).__name__}
            if isinstance(data,dict):
                summary["keys"]=list(data)[:40]
                summary["value_types"]={k:type(v).__name__ for k,v in list(data.items())[:20]}
                for k,v in data.items():
                    if isinstance(v,list):
                        summary[k+"_size"]=len(v)
                        if v and isinstance(v[0],dict):summary[k+"_example_keys"]=list(v[0])[:30]
            if isinstance(data,list):
                summary["rows"]=len(data)
                if data and isinstance(data[0],dict):summary["example_keys"]=list(data[0])[:40]
            report["results"][conf][path]=summary
    (out/"api_probe_summary.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=="__main__":run("data/availability_api_probe")
