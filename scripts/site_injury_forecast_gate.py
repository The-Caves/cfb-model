"""Source-timed, game-specific injury / availability PICK ELIGIBILITY gate.

This is *not* a numerical replacement-value estimate. V04/V14 means, existing
picks, player forecasts, historical grades and betting prices are unchanged.
It identifies when current roster information makes their unconditioned
forecast unsuitable for a confident pick. Counts do NOT imply expected points.
Reports are accepted only if observed <= decision < kickoff; unreported means
UNKNOWN, never AVAILABLE. Every future point adjustment requires separately
validated player/position replacement value and first-seen evidence.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from scripts.game_context import parse_time

STATUS="ROSTER_AWARE_MODEL_ELIGIBILITY_RESEARCH_ONLY"
ALERT_QB={"OUT","SUSPENDED","DOUBTFUL","OUT_FIRST_HALF",
          "QUESTIONABLE","GAME_TIME_DECISION","LIMITED","CONFLICT_REVIEW"}
OUT={"OUT","SUSPENDED","OUT_FIRST_HALF"}
MAJOR_POS={"QB","OL","DL","EDGE","WR","RB","TE","CB","LB","S","DB"}
QB_OFFICIAL="OFFICIAL_SEASON_OUT_VERIFIED_AFTER_SOURCE_REVIEW"


def _verified_report(row,now,kickoff):
    if not isinstance(row,dict) or not row.get("player"):
        return False
    if (row.get("source_type")!="OFFICIAL_CONFERENCE_AVAILABILITY" or
        row.get("not_starter_confirmation") is not True or
        not str(row.get("source_url") or "").startswith("https://")):
        return False
    try:
        publication=parse_time(row["published_at_utc"])
        observation=parse_time(row["observed_at_utc"])
    except (ValueError,KeyError,TypeError):
        return False
    return publication<=observation<=now<kickoff


def _longterm(row,now,kickoff):
    if (not isinstance(row,dict) or row.get("status")!=QB_OFFICIAL or
        row.get("designation")!="OUT_REMAINDER_2026" or
        row.get("source_type")!="OFFICIAL_UNIVERSITY_STATEMENT" or
        row.get("replacement_value_calibrated") is not False or
        row.get("changes_frozen_score") is not False or
        not str(row.get("source_url") or "").startswith("https://")):
        return False
    try:
        first=parse_time(row["first_eligible_at_utc"])
    except (KeyError,ValueError,TypeError):
        return False
    return first<=now<kickoff


def _side(game,side,now,kickoff):
    qb=game.get("qb_"+side) or {}
    absent=game.get("official_longterm_qb_absences_"+side) or []
    if not isinstance(absent,list):
        raise ValueError("Invalid official QB outage list")
    reports=game.get("qb_availability_"+side) or []
    rest=game.get("player_availability_"+side) or []
    if not isinstance(reports,list) or not isinstance(rest,list):
        raise ValueError("Invalid source-observed player availability list")
    verified_absent=[r for r in absent if _longterm(r,now,kickoff)]
    byplayer={}
    for row in reports+rest:
        if not _verified_report(row,now,kickoff):
            continue
        key=(row.get("player","").strip().casefold(),row.get("position"))
        prev=byplayer.get(key)
        if prev and prev["published_at_utc"]==row["published_at_utc"] and prev["status"]!=row["status"]:
            byplayer[key]={**row,"status":"CONFLICT_REVIEW"}
        elif (prev is None or
              row["published_at_utc"]>prev["published_at_utc"] or
              (row["published_at_utc"]==prev["published_at_utc"] and
               row["observed_at_utc"]>prev["observed_at_utc"])):
            byplayer[key]=row
    valid=sorted(byplayer.values(),key=lambda r:(r["position"],r["player"]))
    qb_alerts=[r for r in valid if r["position"]=="QB" and r["status"] in ALERT_QB]
    nonqb=[r for r in valid if r["position"]!="QB" and r["status"] in
           OUT|{"DOUBTFUL","QUESTIONABLE","GAME_TIME_DECISION","CONFLICT_REVIEW"}]
    # A verified roster report does not prove a player is QB1, a starter or
    # a high-snap contributor. We flag, but do not fabricate an impact.
    qb_claim=(qb.get("player") or "").strip().casefold()
    expected=(game.get("qb_pregame_"+side) or {}).get("player")
    expected=(expected or "").strip().casefold()
    suspect={r["player"].strip().casefold() for r in qb_alerts}
    key_status=(
        "STARTER_IDENTITY_CONFLICT" if qb.get("status")=="CONFLICT_REVIEW" else
        "VERIFIED_LONGTERM_QB_OUT_UNCALIBRATED" if verified_absent else
        "EXPECTED_QB_HAS_ACTIONABLE_REPORT" if qb_claim in suspect or expected in suspect else
        "QB_STATUS_REPORTED_ROLE_UNVERIFIED" if qb_alerts else
        "NON_QB_REPORTED_EFFECT_UNCALIBRATED" if nonqb else
        "NO_ACTIONABLE_VERIFIED_ISSUE_DETECTED")
    high=key_status in ("STARTER_IDENTITY_CONFLICT",
                       "VERIFIED_LONGTERM_QB_OUT_UNCALIBRATED",
                       "EXPECTED_QB_HAS_ACTIONABLE_REPORT")
    return {
        "team":game[side+"_team"],"side":side,
        "status":key_status,
        "requires_qb_review_before_pick":high,
        "verified_replacement_starter":(
            qb.get("status")=="CONFIRMED_OFFICIAL" and
            bool(qb_claim) and qb_claim not in
            {r["player"].strip().casefold() for r in verified_absent} and
            qb_claim not in suspect),
        "expected_qb":qb.get("player") or expected or None,
        "qb_source_status":qb.get("status","UNKNOWN"),
        "confirmed_longterm_absences":[{
            "player":r["player"],"position":"QB","status":"OUT",
            "source_url":r["source_url"],
            "first_eligible_at_utc":r["first_eligible_at_utc"]}
            for r in verified_absent],
        "actionable_qb_reports":[{
            "player":r["player"],"status":r["status"],"position":"QB",
            "source_url":r["source_url"],"published_at_utc":r["published_at_utc"],
            "observed_at_utc":r["observed_at_utc"]}
            for r in qb_alerts],
        "other_actionable_reports":[{
            "player":r["player"],"position":r["position"],"status":r["status"],
            "source_url":r["source_url"],"published_at_utc":r["published_at_utc"],
            "observed_at_utc":r["observed_at_utc"],
            "starting_role_confirmed":False,
            "point_replacement_value_known":False}
            for r in nonqb if r["position"] in MAJOR_POS],
        "no_fabricated_points":True,
        "not_listed_is_not_available":True,
    }


def attach(board,now):
    instant=parse_time(now)
    if (board.get("schema_version")!=2 or
        board.get("betting_status")!="PASS_UNVALIDATED" or
        not isinstance(board.get("games"),list)):
        raise ValueError("Untrusted CFB dashboard source")
    before=json.dumps([{
        "v04":g.get("v04_direct_scores"),
        "v13":g.get("v13_probability_shadow"),
        "v14":g.get("v14_matchup_shadow"),
        "spread":g.get("model_ats_side"),"total":g.get("model_ou_side"),
        "m":g.get("model_home_margin"),"t":g.get("model_total"),
        "players":g.get("player_stat_outlook")}
        for g in board["games"]],sort_keys=True)
    seen=set()
    summary={"review_qb":0,"review_other_positions":0,
             "no_verified_roster_impact":0,"already_started":0}
    for g in board["games"]:
        gid=str(g["game_id"])
        if gid in seen:raise ValueError("Duplicate source game identity")
        seen.add(gid)
        kickoff=parse_time(g["kickoff_utc"])
        g["roster_model_eligibility"]=None
        if instant>=kickoff:
            summary["already_started"]+=1
            continue
        sides={side:_side(g,side,instant,kickoff) for side in ("home","away")}
        high=any(x["requires_qb_review_before_pick"] for x in sides.values())
        other=any(x["other_actionable_reports"] for x in sides.values())
        status=("PASS_QB_STATUS_OR_REPLACEMENT_UNRESOLVED" if high else
                "PASS_VERIFIED_NON_QB_EFFECT_UNCALIBRATED" if other else
                "PASS_NO_VALIDATED_PERSONNEL_EFFECT")
        g["roster_model_eligibility"]={
            "status":STATUS,"game_id":gid,
            "asof_utc":instant.isoformat(),
            "kickoff_utc":g["kickoff_utc"],"home":g["home_team"],"away":g["away_team"],
            "model_source":"V04_V14_UNCONDITIONED_BY_ROSTER",
            "sides":sides,
            "injury_sensitive_ats_action":status,
            "injury_sensitive_total_action":status,
            "injury_sensitive_player_prop_action":status,
            "cannot_claim_current_roster_adjusted_projection":True,
            "confirmed_absence_not_an_estimated_point_penalty":True,
            "original_scores_and_market_picks_unchanged":True,
            "nonqb_starting_roles_not_verified":True,
            "unknown_is_not_healthy":True,
            "model_promoted":False,"safe_for_betting":False}
        summary["review_qb"]+=int(high)
        summary["review_other_positions"]+=int(other)
        summary["no_verified_roster_impact"]+=int(not(high or other))
    after=json.dumps([{
        "v04":g.get("v04_direct_scores"),
        "v13":g.get("v13_probability_shadow"),
        "v14":g.get("v14_matchup_shadow"),
        "spread":g.get("model_ats_side"),"total":g.get("model_ou_side"),
        "m":g.get("model_home_margin"),"t":g.get("model_total"),
        "players":g.get("player_stat_outlook")}
        for g in board["games"]],sort_keys=True)
    if before!=after:raise ValueError("Injury overlay rewrote original score or market pick")
    board["roster_model_eligibility_summary"]={
        "status":STATUS,**summary,
        "original_scores_and_market_picks_unchanged":True,
        "source_reports_not_proof_of_player_starting_role":True,
        "source_data_first_seen_no_future_leakage":True,
        "no_calibrated_replacement_value":True,
        "independent_injury_scoring_improvement_proven":False}
    return board


def run(dashboard,now=None):
    path=Path(dashboard)
    board=json.loads(path.read_text())
    instant=now or dt.datetime.now(dt.timezone.utc).isoformat()
    result=attach(board,instant)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result["roster_model_eligibility_summary"],sort_keys=True))
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--dashboard",required=True)
    a=parser.parse_args()
    run(a.dashboard)
