"""Predecision ESPN athlete ID join and non-snap offensive/defensive role proxies.

Matches same-season ESPN player IDs and team IDs, detects prior-team 2025
transfers, and exports ONLY reviewable *usage opportunities*. Position and
opportunity shares do not imply snap percentage, healthy roster or ability.
No injuries are inferred. Every source is captured now, NEVER backdated.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import math
from collections import Counter,defaultdict
from pathlib import Path

from scripts.nextgen_source_readiness import ASSETS,fetch_asset,SOURCE

STATUS="SOURCE_OBSERVED_PLAYER_ROLE_CROSSWALK_RESEARCH_ONLY"
RULES={"RB":("touch_share","TEAM_TOUCH_SHARE"),
       "WR":("target_share","TEAM_TARGET_SHARE"),
       "TE":("target_share","TEAM_TARGET_SHARE"),
       "DL":("tackle_share","SCRIMMAGE_TACKLE_SHARE"),
       "EDGE":("tackle_share","SCRIMMAGE_TACKLE_SHARE"),
       "LB":("tackle_share","SCRIMMAGE_TACKLE_SHARE"),
       "CB":("tackle_share","SCRIMMAGE_TACKLE_SHARE"),
       "DB":("tackle_share","SCRIMMAGE_TACKLE_SHARE"),
       "S":("tackle_share","SCRIMMAGE_TACKLE_SHARE")}
FIELDS={
 "roster_2025":["season","team_id","athlete_id"],
 "roster_2026":["season","team_id","athlete_id"],
 "offense_usage_2026":["season","pos_team_id","player_id","position_group",
                       "games","target_share","touch_share"],
 "defense_usage_2026":["season","def_pos_team_id","player_id","position_group",
                       "games","tackle_share"],
}
def _id(x):
    if isinstance(x,bool):return None
    token=str(x or "").strip()
    try:
        numeric=float(token)
    except ValueError:return None
    if not numeric.is_integer() or numeric<=0 or not math.isfinite(numeric):return None
    return str(int(numeric))

def _share(value):
    return type(value) in (int,float) and math.isfinite(value) and 0<=value<=1

def audit(rows,issue,source_hashes):
    by_year={}
    collisions=0
    for year in (2025,2026):
        lookup=defaultdict(set)
        for r in rows["roster_"+str(year)]:
            if int(r.get("season") or 0)!=year:continue
            pid,team=_id(r.get("athlete_id")),_id(r.get("team_id"))
            if pid and team:lookup[pid].add(team)
        by_year[year]=lookup
        collisions+=sum(len(teams)>1 for teams in lookup.values())
    current={(team,pid) for pid,teams in by_year[2026].items() for team in teams
             if len(teams)==1}
    covered=[];rejected=Counter();seen=set()
    for kind in ("offense_usage_2026","defense_usage_2026"):
        for r in rows[kind]:
            pid=_id(r.get("player_id"))
            team=_id(r.get("pos_team_id" if kind=="offense_usage_2026" else "def_pos_team_id"))
            pos=str(r.get("position_group") or "").upper().strip()
            key=(kind,team,pid)
            if not pid or not team or key in seen:
                rejected["MISSING_OR_DUPLICATE_PLAYER_TEAM_ID"]+=1;continue
            seen.add(key)
            if (team,pid) not in current:
                rejected["NO_UNAMBIGUOUS_CURRENT_SEASON_ROSTER_ID_MATCH"]+=1;continue
            if pos not in RULES:
                rejected["POSITION_NOT_A_SUPPORTED_USAGE_PROXY"]+=1;continue
            field,unit=RULES[pos]
            if kind=="offense_usage_2026" and field=="tackle_share":
                rejected["WRONG_USAGE_SOURCE_FOR_POSITION"]+=1;continue
            if kind=="defense_usage_2026" and field!="tackle_share":
                rejected["WRONG_USAGE_SOURCE_FOR_POSITION"]+=1;continue
            share=r.get(field);games=r.get("games")
            if not _share(share) or type(games) not in (int,float) or games<2:
                rejected["INSUFFICIENT_PLAYER_OPPORTUNITY_SAMPLE"]+=1;continue
            previous=sorted(t for t in by_year[2025].get(pid,set()) if t!=team)
            covered.append({
                "player_id":pid,"team_id":team,"position_group":pos,
                "role_share":round(float(share),6),"role_share_basis":unit,
                "games_with_observed_opportunities":int(games),
                "source_observed_at_utc":issue,
                "source_sha256":source_hashes[kind],
                "roster_source_sha256":source_hashes["roster_2026"],
                "player_identity_crosswalk_verified_for_team":True,
                "previous_2025_team_ids":previous,
                "transfer_status":"PRIOR_TEAM_DIFFERENT_NOT_TRANSFER_ELIGIBILITY_VERIFIED"
                                  if previous else "NO_DIFFERENT_2025_TEAM_OBSERVED",
                "is_snap_share":False,"starting_status_confirmed":False,
                "injury_status_verified":False,
            })
    covered.sort(key=lambda x:(x["team_id"],x["player_id"],x["role_share_basis"]))
    counts=dict(Counter(x["role_share_basis"] for x in covered))
    return {"status":STATUS,"season":2026,"captured_at_utc":issue,
       "source_checksums":source_hashes,
       "same_season_ambiguous_player_id_count":collisions,
       "roster_2026_unique_athletes":len(by_year[2026]),
       "eligible_role_records":len(covered),
       "eligible_role_types":counts,
       "rejected_role_rows_by_reason":dict(rejected),
       "role_records":covered,
       "evidence_semantics":{
           "opportunity_usage_not_actual_snap_percentage":True,
           "roster_source_does_not_confirm_starter_or_health":True,
           "prior_team_ID_does_not_prove_transfer_eligibility":True,
           "no_point_penalties_learned_or_applied":True,
           "cannot_backfill_earlier_decisions_from_current_season_totals":True},
       "model_promoted":False,"safe_for_betting":False,
       "betting_status":"PASS_UNVALIDATED"}

def run(out):
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    sources={};hashes={};errors={}
    import pyarrow.parquet as pq
    for name,cols in FIELDS.items():
        try:
            url=SOURCE+"/"+ASSETS[name][0]
            blob=fetch_asset(url)
            hashes[name]=hashlib.sha256(blob).hexdigest()
            obj=pq.read_table(io.BytesIO(blob),columns=cols)
            sources[name]=obj.to_pylist()
        except Exception as exc:
            errors[name]=type(exc).__name__+":"+str(exc)[:180]
    if errors:
        result={"status":"PASS_UNAVAILABLE_SOURCE_ROLE_CROSSWALK",
                "captured_at_utc":now,"source_failures":errors,
                "role_records":[],"model_promoted":False,
                "betting_status":"PASS_UNVALIDATED"}
    else:
        result=audit(sources,now,hashes)
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],
           "eligible_role_records":len(result["role_records"]),
           "eligible_role_types":result.get("eligible_role_types",{}),
           "source_failures":result.get("source_failures",{}),
           "model_promoted":False}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",required=True)
    run(p.parse_args().output)
