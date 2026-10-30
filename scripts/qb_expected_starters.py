"""Observed expected-starter and QB1/QB2/QB3 research slate.

A named last-game passer is NOT a verified next starter; a third-party depth
chart rank is NOT a confirmation. Report source, confidence and conflicts.
Do not invent injury status from missing player reports or make QB2 worse than QB1.
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path
from scripts.game_context import parse_time
from scripts.site_depthchart import chart_for_teams,normalized,allowed,SOURCE
from scripts.qb_role_features import STATUS as ROLE_STATUS

STATUS="QB_EXPECTED_STARTER_SOURCE_RANKED_RESEARCH_ONLY"
INACTIVE={"OUT","SUSPENDED"}
START_UNAVAILABLE=INACTIVE|{"OUT_FIRST_HALF"}  # Cannot start; may return after halftime.
WARN={"QUESTIONABLE","DOUBTFUL","GAME_TIME_DECISION","LIMITED"}
MAX_CHART_AGE_DAYS=21

def _name(x):
    if not x:return None
    # E.J. Archield and EJ Archield are the same initials, not two QB IDs.
    cleaned=re.sub(r"\b([A-Za-z])\.\s*(?=[A-Za-z]\.)",r"\1",x)
    return normalized(cleaned)

def _availability(game,team,decision):
    out={}
    for row in game.get("qb_availability_reports") or []:
        if row.get("team")!=team or row.get("position")!="QB":continue
        if row.get("status") not in INACTIVE|WARN|{"AVAILABLE","PROBABLE","UNKNOWN"}:
            continue
        if not row.get("player"):continue
        try:
            pub=parse_time(row["published_at_utc"])
            obs=parse_time(row["captured_at_utc"])
        except (KeyError,TypeError,ValueError):continue
        if not pub<=obs<=decision<parse_time(game["kickoff_utc"]):continue
        key=_name(row["player"])
        if key in out and out[key]["captured_at_utc"]==row["captured_at_utc"] and out[key]["status"]!=row["status"]:
            out[key]={"status":"CONFLICT","captured_at_utc":row["captured_at_utc"]}
        elif key not in out or parse_time(out[key]["captured_at_utc"])<obs:
            out[key]={"status":row["status"],"captured_at_utc":row["captured_at_utc"],
                      "source_url":row.get("source_url")}
    return out

def build(context,role,charts,observed_at_utc,chart_health=None):
    decision=parse_time(observed_at_utc)
    if role.get("status")!=ROLE_STATUS or role.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Unverified historical QB role evidence")
    if parse_time(role["asof_utc"])>decision or parse_time(context["asof_utc"])>decision:
        raise ValueError("QB sources after target decision")
    index={(str(r["game_id"]),r["team"]):r for r in role["rows"]}
    if len(index)!=len(role["rows"]):raise ValueError("Duplicate QB role/fixture")
    out=[];seen=set()
    for g in context["games"]:
        gid=str(g["game_id"]);kickoff=parse_time(g["kickoff_utc"])
        if kickoff<=decision:continue
        for side in ("home","away"):
            team=g[side];other=g["away" if side=="home" else "home"]
            key=(gid,team)
            if key in seen:raise ValueError("Duplicate game/team")
            seen.add(key)
            historical=index.get(key)
            if historical is None or (historical["opponent"],parse_time(historical["kickoff_utc"]))!=(other,kickoff):
                raise ValueError("QB role and upcoming game mismatch")
            source=charts.get(team)
            ranked=[];chart_status="UNKNOWN_NO_CHART"
            if source is not None:
                captured=parse_time(source["observed_at_utc"])
                if (source.get("source_type")!=SOURCE or
                    not allowed(source.get("source_url","")) or
                    captured>decision or captured>=kickoff or
                    (decision-captured).days>MAX_CHART_AGE_DAYS or
                    not isinstance(source.get("players"),list)):
                    raise ValueError("Untrusted, stale or postkickoff depth chart")
                names=[n for n in source["players"][:3] if isinstance(n,str) and _name(n)]
                if len(names)!=len(source["players"][:3]) or len({_name(n) for n in names})!=len(names):
                    raise ValueError("Ambiguous depth-chart order")
                ranked=[{"player":n,"rank":i+1,"label":f"QB{i+1}"}
                        for i,n in enumerate(names)]
                chart_status="THIRD_PARTY_DEPTH_CHART_NOT_STARTER_CONFIRMATION"
            availability=_availability(g,team,decision)
            official=(g.get("verified_qb_starters") or {}).get(team)
            verified=historical.get("current_starting_qb")
            if verified and official and _name(official.get("player"))!=_name(verified):
                raise ValueError("Contradictory confirmed starting QB")
            if verified:
                current={"player":verified,"source_class":"CONFIRMED_REVIEWED_PREKICKOFF",
                         "confidence":"HIGH_OFFICIAL","reason":"REVIEWED_EXPLICIT_GAME_WEEK_STARTER"}
            else:
                # An OUT designation is only sourced when published before
                # decision; no report means availability UNKNOWN, not healthy.
                qb1=ranked[0]["player"] if ranked else None
                qb1_status=availability.get(_name(qb1),{}).get("status") if qb1 else None
                latest=historical.get("last_game_leading_passer_proxy")
                latest_rank=next((r["rank"] for r in ranked
                                  if _name(r["player"])==_name(latest)),None)
                if qb1 and qb1_status in START_UNAVAILABLE:
                    alternatives=[r for r in ranked[1:] if availability.get(_name(r["player"]),{}).get("status") not in START_UNAVAILABLE|{"CONFLICT"}]
                    if latest_rank and latest_rank>1 and any(_name(r["player"])==_name(latest) for r in alternatives):
                        # Recently active QB2/3 becomes an expected, NOT confirmed starter.
                        current={"player":latest,"source_class":"PROJECTED_FROM_QB1_OUT_AND_LAST_GAME_PASSER",
                                 "confidence":"MEDIUM_UNCONFIRMED","reason":"INACTIVE_CHART_QB1_AND_LATEST_PASSER"}
                    elif alternatives:
                        # Chart position is only a provisional replacement prior;
                        # its rank is not proof that this player will start.
                        current={"player":alternatives[0]["player"],
                                 "source_class":"PROJECTED_AVAILABLE_BACKUP_AFTER_QB1_OUT",
                                 "confidence":"LOW_UNCONFIRMED",
                                 "reason":"QB1_OUT_QB2_CHART_ALTERNATIVE_NO_STARTER_STATEMENT"}
                    else:
                        current={"player":None,"source_class":"UNKNOWN",
                                 "confidence":"UNKNOWN","reason":"CHART_QB1_OUT_WITH_NO_VERIFIED_REPLACEMENT"}
                elif qb1 and latest and _name(qb1)==_name(latest):
                    current={"player":qb1,"source_class":"PROJECTED_CHART_QB1_AND_LAST_GAME",
                             "confidence":"MEDIUM_UNCONFIRMED" if qb1_status not in WARN else "LOW_UNCONFIRMED",
                             "reason":"CHART_AND_RECENT_PASSING_USAGE_AGREE"}
                elif qb1 and latest and _name(qb1)!=_name(latest):
                    # Ourlads charts can predate an actual QB return (Delaware
                    # Oct23 chart versus Oct27 observed player participation).
                    # In that case recent real play is a more current
                    # *expectation* than the stale order, not confirmation.
                    updated=source.get("source_updated_et") if source else None
                    last=historical.get("last_game_passer_date")
                    chart_stale=False
                    if updated and last:
                        at=parse_time(updated)
                        chart_stale=dt.date.fromisoformat(last)>at.date()
                    same_two=(historical.get("recent_two_game_leading_passer_proxy")
                              and _name(historical["recent_two_game_leading_passer_proxy"])==_name(latest))
                    latest_status=availability.get(_name(latest),{}).get("status")
                    if chart_stale and latest_status not in START_UNAVAILABLE|{"CONFLICT"}:
                        current={"player":latest,
                                 "source_class":"PROJECTED_RECENT_PASSER_AFTER_STALE_CHART",
                                 "confidence":"MEDIUM_UNCONFIRMED",
                                 "reason":"LAST_GAME_PASSER_NEWER_THAN_DEPTH_CHART_UPDATE"}
                    elif not updated and same_two and latest_status not in START_UNAVAILABLE|{"CONFLICT"}:
                        # The provider chart was fetched recently, but without
                        # a dated chart update that is NOT evidence it superseded
                        # two consecutive actual games of passing usage.
                        current={"player":latest,
                                 "source_class":"PROJECTED_TWO_GAME_PASSER_VS_UNDATED_CHART",
                                 "confidence":"LOW_UNCONFIRMED",
                                 "reason":"TWO_CONSECUTIVE_DOMINANT_PASSER_GAMES_CHART_UNDATED"}
                    else:
                        # Explicitly updated postgame charts override usage-only
                        # inference. One recent game may be a spot substitution.
                        current={"player":None,"source_class":"CONFLICT_CHART_VS_RECENT_QB",
                                 "confidence":"UNKNOWN","reason":"QB1_CHART_DIFFERS_FROM_RECENT_GAME_PASSER"}
                elif qb1:
                    current={"player":qb1,"source_class":"PROJECTED_DEPTH_CHART_ONLY",
                             "confidence":"LOW_UNCONFIRMED","reason":"CHART_QB1_NO_RECENT_USAGE_CONFIRMATION"}
                elif latest and availability.get(_name(latest),{}).get("status") not in START_UNAVAILABLE|{"CONFLICT"}:
                    current={"player":latest,"source_class":"PROJECTED_LAST_GAME_PASSER_ONLY",
                             "confidence":"LOW_UNCONFIRMED","reason":"LAST_GAME_PASSER_NOT_GAME_WEEK_STARTER"}
                else:
                    current={"player":None,"source_class":"UNKNOWN",
                             "confidence":"UNKNOWN","reason":"NO_SOURCE_NAMED_EXPECTED_STARTER"}
            depth_rank=next((r["rank"] for r in ranked
                             if _name(r["player"])==_name(current["player"])),None)
            options=[]
            # Even if the predicted starter is unknown, preserve QB1/QB2/QB3
            # as independently evaluated *scenarios*, with separate stats.
            for r in ranked:
                if availability.get(_name(r["player"]),{}).get("status") in INACTIVE:
                    continue
                options.append({"player":r["player"],"depth_rank":r["rank"],
                                "role":r["label"],"source":"THIRD_PARTY_CHART_SCENARIO",
                                "opening_start_eligible":
                                    availability.get(_name(r["player"]),{}).get("status") not in START_UNAVAILABLE,
                                "out_first_half":
                                    availability.get(_name(r["player"]),{}).get("status")=="OUT_FIRST_HALF"})
            if current["player"] and _name(current["player"]) not in {_name(r["player"]) for r in options}:
                options.append({"player":current["player"],"depth_rank":depth_rank,
                                "role":f"QB{depth_rank}" if depth_rank else "QB_RANK_UNKNOWN",
                                "source":current["source_class"]})
            # This is not the certainty the user asked for; it is an auditable
            # provisional report that allows the model to use conditioned form.
            out.append({"game_id":gid,"team":team,"opponent":other,"side":side,
                "kickoff_utc":g["kickoff_utc"],"observed_at_utc":decision.isoformat(),
                "starter":current["player"],"starter_status":current["source_class"],
                "confidence":current["confidence"],"reason":current["reason"],
                "depth_rank":depth_rank,"depth_label":f"QB{depth_rank}" if depth_rank else "UNKNOWN",
                "chart_status":chart_status,"depth_chart":ranked,
                "last_game_passer_date":historical.get("last_game_passer_date"),
                "last_game_passer_share_named":historical.get("last_game_passer_share_named"),
                "recent_two_game_leading_passer_proxy":historical.get("recent_two_game_leading_passer_proxy"),
                "depth_chart_updated_et":source.get("source_updated_et") if source else None,
                "chart_source_url":source.get("source_url") if source else None,
                "official_recent_return_context":historical.get("official_recent_return_context"),
                "last_game_leading_passer_proxy":historical.get("last_game_leading_passer_proxy"),
                "season_leading_passer_proxy":historical.get("season_leading_passer_proxy"),
                "availability_by_player":availability,"scenarios":options,
                "is_confirmed_starter":current["source_class"]=="CONFIRMED_REVIEWED_PREKICKOFF",
                "uncertainty_not_zero":True,"betting_status":"PASS_UNVALIDATED"})
    result={"status":STATUS,"season":2026,"observed_at_utc":decision.isoformat(),
        "source_role_asof_utc":role["asof_utc"],"chart_collection_health":chart_health or {},
        "team_slots":len(out),"games":out,"summary":{
            "projected_or_confirmed_starters":sum(bool(r["starter"]) for r in out),
            "confirmed_starters":sum(r["is_confirmed_starter"] for r in out),
            "charted_teams":sum(bool(r["depth_chart"]) for r in out),
            "unknown_starters":sum(not r["starter"] for r in out),
            "conflicting_chart_vs_last_game":sum(r["starter_status"]=="CONFLICT_CHART_VS_RECENT_QB" for r in out)},
        "model_promoted":False,"safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
    return result

def run(context_path,role_path,aliases_path,output_path,charts_path=None):
    context=json.loads(Path(context_path).read_text())
    role=json.loads(Path(role_path).read_text())
    now=dt.datetime.now(dt.timezone.utc)
    charts={};health={}
    if charts_path:
        cache=json.loads(Path(charts_path).read_text())
        charts=cache["charts"];health=cache.get("coverage",{})
    else:
        # Use existing Ourlads collector, but do not conflate page rank with
        # next-game starter confirmation. Network failure remains UNKNOWN.
        board={"schema_version":2,"betting_status":"PASS_UNVALIDATED",
               "games":[{"game_id":g["game_id"],"home_team":g["home"],
                         "away_team":g["away"],"kickoff_utc":g["kickoff_utc"]}
                        for g in context["games"] if parse_time(g["kickoff_utc"])>now]}
        try:charts,health=chart_for_teams(board,aliases_path)
        except (OSError,ValueError,TimeoutError) as exc:
            health={"status":"DEPTH_SOURCE_UNAVAILABLE","error_kind":type(exc).__name__}
    finished=dt.datetime.now(dt.timezone.utc).isoformat()
    result=build(context,role,charts,finished,health)
    out=Path(output_path);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("x") as f:json.dump(result,f,indent=2,allow_nan=False);f.write("\n")
    print(json.dumps({"status":STATUS,**result["summary"],"chart_health":health}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--context",required=True);p.add_argument("--role",required=True)
    p.add_argument("--aliases",default="data/archive/2026_team_aliases.csv")
    p.add_argument("--charts");p.add_argument("--output",required=True)
    a=p.parse_args();run(a.context,a.role,a.aliases,a.output,a.charts)
