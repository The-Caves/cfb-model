"""Inspect actual ESPN-completed game possession schemas before fitting drives."""
import argparse,datetime as dt,json
from pathlib import Path
from scripts.turnover_boxscore import URL,fetch,parse as verify_box

def inspect(gid):
    data=fetch(gid)
    header=(data.get("header") or {}).get("competitions") or []
    drives=data.get("drives") or {}
    first=header[0] if header else {}
    teams=first.get("competitors") or []
    res={
      "game_id":str(gid),
      "captured_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "top_keys":list(data),
      "header_fields":list(first),
      "competitors":[{"homeAway":x.get("homeAway"),"team":x.get("team",{}).get("displayName"),
                      "score":x.get("score"),"team_id":x.get("team",{}).get("id")} for x in teams],
      "drives_container_keys":list(drives),
      "previous_drives":len(drives.get("previous") or []),
      "drive_samples":[{"keys":list(x),"id":x.get("id"),"team":x.get("team"),
        "start":x.get("start"),"end":x.get("end"),"result":x.get("result"),
        "isScore":x.get("isScore"),"yards":x.get("yards"),"offensivePlays":x.get("offensivePlays"),
        "plays_length":len(x.get("plays") or []),
        "sample_plays":[{"keys":list(p),"id":p.get("id"),"type":p.get("type"),
          "homeScore":p.get("homeScore"),"awayScore":p.get("awayScore"),
          "scoringPlay":p.get("scoringPlay"),"text":p.get("text"),
          "team":p.get("team"),"start":p.get("start"),"end":p.get("end")}
          for p in (x.get("plays") or [])[:2]]}
        for x in (drives.get("previous") or [])[:5]],
      "scoring_plays_count":len(data.get("scoringPlays") or []),
      "scoring_plays_sample":(data.get("scoringPlays") or [])[:3],
      "boxscore_verified_turnovers":None,
      "error":None,
    }
    g={"game_id":str(gid),
       "home":next((x.get("team",{}).get("displayName") for x in teams if x.get("homeAway")=="home"),""),
       "away":next((x.get("team",{}).get("displayName") for x in teams if x.get("homeAway")=="away"),""),
       "home_score":next((x.get("score") for x in teams if x.get("homeAway")=="home"),""),
       "away_score":next((x.get("score") for x in teams if x.get("homeAway")=="away"),""),
       "date":(first.get("date") or "")[:10]}
    try:res["boxscore_verified_turnovers"]=verify_box(g,data,res["captured_at_utc"])
    except (ValueError,TypeError,KeyError) as exc:res["error"]=str(exc)
    return res

def run(gids,output):
    result={"games":[]}
    for gid in gids:
        try:result["games"].append(inspect(gid))
        except (OSError,ValueError,TypeError,KeyError) as ex:
            result["games"].append({"game_id":str(gid),"fetch_error":type(ex).__name__,"detail":str(ex)[:180]})
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps([{"gid":r.get("game_id"),"drives":r.get("previous_drives"),
                        "error":r.get("fetch_error"),"keys":r.get("drives_container_keys")}
                        for r in result["games"]]))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--ids",nargs="+",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.ids,a.output)
