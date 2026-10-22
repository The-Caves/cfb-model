"""Point-in-time 2026 QB evidence history; UNKNOWN is the safe default.

Snapshots are *observed* game-team records, not automatic starter predictions.
Official news candidates, QB availability and team history are NEVER promoted
into starter confirmations without a reviewed, game-specific official source.
"""
import argparse,datetime as dt,json
from pathlib import Path
from urllib.parse import urlsplit
from scripts.game_context import parse_time
from scripts.weekly_profiles import canonical,digest

STATUS="QB_HISTORY_RESEARCH_ONLY"
SOURCE_TYPES={"OFFICIAL_TEAM_RELEASE","ON_RECORD_COACH_CONFIRMATION"}
def _time(x):
    return parse_time(x)
def _slot(game,team,opponent,obs,queue_row):
    kickoff=_time(game["kickoff_utc"])
    record={"game_id":str(game["game_id"]),"team":team,"opponent":opponent,
            "kickoff_utc":game["kickoff_utc"],"observed_at_utc":obs.isoformat(),
            "starter_status":"UNKNOWN","starter_player":None,
            "starter_evidence":None,"qb_availability_signals":[],
            "review_candidate_count":0,"evidence_conflicts":[]}
    if queue_row:
        record["review_candidate_count"]=queue_row["candidate_count"]
    for a in game.get("qb_availability_reports",[]):
        if not isinstance(a,dict) or a.get("team")!=team or a.get("position")!="QB":
            continue
        pub=a.get("published_at_utc");capture=a.get("captured_at_utc")
        try:
            if pub is None or capture is None or not (_time(pub)<=_time(capture)<=obs<kickoff):
                record["evidence_conflicts"].append("INVALID_QB_AVAILABILITY_TIME")
                continue
        except (TypeError,ValueError):
            record["evidence_conflicts"].append("INVALID_QB_AVAILABILITY_TIME")
            continue
        record["qb_availability_signals"].append({
            "player":a.get("player"),"status":a.get("status","UNKNOWN"),
            "published_at_utc":pub,"captured_at_utc":capture,
            "source_url":a.get("source_url")})
    confirmed=(game.get("verified_qb_starters") or {}).get(team)
    if confirmed:
        player=str(confirmed.get("player","")).strip()
        url=urlsplit(str(confirmed.get("source_url","")))
        pub=confirmed.get("published_at_utc")
        capture=confirmed.get("captured_at_utc")
        reviewed=confirmed.get("reviewed_at_utc")
        try:
            chron=(pub is not None and capture is not None and reviewed is not None
                   and _time(pub)<=_time(capture)<=_time(reviewed)<=obs<kickoff
                   and (kickoff-_time(pub)).total_seconds()<=14*86400)
        except (ValueError,TypeError):
            chron=False
        source_valid=(
            chron and 3<=len(player)<=100
            and confirmed.get("source_type") in SOURCE_TYPES
            and confirmed.get("evidence_scope")=="EXPLICIT_THIS_GAME"
            and url.scheme=="https" and bool(url.hostname)
            and not url.username and not url.password)
        if not source_valid:
            record["evidence_conflicts"].append("UNSUPPORTED_OR_LATE_STARTER_CLAIM")
        elif any(s["player"]==player and s["status"] in
                 ("OUT","SUSPENDED","DOUBTFUL","LIMITED")
                 for s in record["qb_availability_signals"]):
            record["evidence_conflicts"].append("CONFIRMED_STARTER_AVAILABILITY_CONFLICT")
        else:
            record["starter_status"]="CONFIRMED_REVIEWED_PREKICKOFF"
            record["starter_player"]=player
            record["starter_evidence"]={
                "source_url":confirmed["source_url"],"source_type":confirmed["source_type"],
                "evidence_scope":confirmed["evidence_scope"],
                "published_at_utc":pub,"captured_at_utc":capture,
                "reviewed_at_utc":reviewed}
    if queue_row and queue_row["starter_status"]=="VERIFIED_SOURCE":
        if record["starter_status"]!="CONFIRMED_REVIEWED_PREKICKOFF" or (
            queue_row.get("starter_player")!=record["starter_player"]):
            record["evidence_conflicts"].append("QUEUE_DISAGREES_WITH_REVIEWED_SOURCE")
            record["starter_status"]="UNKNOWN"
            record["starter_player"]=None
            record["starter_evidence"]=None
    if record["evidence_conflicts"] and record["starter_status"]=="CONFIRMED_REVIEWED_PREKICKOFF":
        record["starter_status"]="UNKNOWN"
        record["starter_player"]=None
        record["starter_evidence"]=None
    return record

def observe(context,review_queue,observed_at):
    """Capture one immutable logical observation for each scheduled game/team.

    Observed-time must follow original context capture and review queue. A
    missing reviewed starter is UNKNOWN, even if earlier team games are known.
    """
    when=_time(observed_at)
    ctx_issue=_time(context["asof_utc"])
    ctx_capture=_time(context["captured_at_utc"])
    review_time=_time(review_queue["asof_utc"])
    if not (ctx_issue<=ctx_capture<=when and review_time<=when):
        raise ValueError("Evidence source is newer than observation")
    if review_queue.get("status")!="QB_REVIEW_RESEARCH_ONLY" or (
        review_queue.get("betting_status")!="PASS_UNVALIDATED"
        or review_queue.get("safe_for_betting") is not False):
        raise ValueError("QB review queue must remain unvalidated")
    idx={}
    for row in review_queue.get("rows",[]):
        key=(str(row["game_id"]),row["team"])
        if key in idx:raise ValueError("Duplicate QB review game/team")
        idx[key]=row
    records=[];seen=set()
    for game in sorted(context.get("games",[]),key=lambda g:(g["kickoff_utc"],str(g["game_id"]))):
        gid=str(game["game_id"])
        if gid in seen:raise ValueError("Duplicate ESPN game ID")
        seen.add(gid)
        if _time(game["kickoff_utc"])<=when:
            continue
        if not game["home"] or not game["away"] or game["home"]==game["away"]:
            raise ValueError("Invalid game opponent identity")
        for team,opponent in ((game["home"],game["away"]),(game["away"],game["home"])):
            records.append(_slot(game,team,opponent,when,idx.get((gid,team))))
    if not records:raise ValueError("No pregame QB slots available")
    if len(records)!=2*len({r["game_id"] for r in records}):
        raise ValueError("Two-team coverage required")
    return {"status":STATUS,"season":2026,"observed_at_utc":when.isoformat(),
            "context_asof_utc":ctx_issue.isoformat(),
            "review_queue_asof_utc":review_time.isoformat(),
            "rows":records,"summary":{
                "game_team_slots":len(records),
                "confirmed_reviewed":sum(r["starter_status"]=="CONFIRMED_REVIEWED_PREKICKOFF" for r in records),
                "unknown":sum(r["starter_status"]=="UNKNOWN" for r in records),
                "slots_with_conflicts":sum(bool(r["evidence_conflicts"]) for r in records),
                "unreviewed_news_candidates":sum(r["review_candidate_count"] for r in records)},
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}

def verify_observation(snapshot):
    """Reject malformed, after-kickoff or future-source records."""
    if snapshot.get("status")!=STATUS or snapshot.get("season")!=2026 or (
        snapshot.get("safe_for_betting") is not False
        or snapshot.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Untrusted QB historical observation")
    asof=_time(snapshot["observed_at_utc"])
    if _time(snapshot["context_asof_utc"])>asof or (
        _time(snapshot["review_queue_asof_utc"])>asof):
        raise ValueError("Future-sourced QB observation")
    if not snapshot.get("rows"):raise ValueError("Empty QB observation")
    unique=set()
    for r in snapshot["rows"]:
        key=(str(r["game_id"]),r["team"])
        if key in unique:raise ValueError("Duplicate game/team observation")
        unique.add(key)
        if _time(r["observed_at_utc"])!=asof or _time(r["kickoff_utc"])<=asof:
            raise ValueError("Postkickoff or mismatched QB observation")
        if r["starter_status"]=="CONFIRMED_REVIEWED_PREKICKOFF":
            evidence=r.get("starter_evidence")
            if not r.get("starter_player") or not evidence or any(
                _time(evidence[field])>asof for field in (
                    "published_at_utc","captured_at_utc","reviewed_at_utc")):
                raise ValueError("Invalid confirmed starter provenance")
        elif r["starter_status"]!="UNKNOWN" or r.get("starter_player") is not None:
            raise ValueError("Unreviewed QB claim promoted")
    return True

def lookup(snapshots,game_id,team,decision_utc):
    """Select ONLY observations known before decision and kickoff.

    Later contradictory confirmed starters for the same game trigger review,
    not silent replacement. This is history of pregame claims, NOT proof the
    named player actually started and NOT a replacement injury diagnosis.
    """
    cut=_time(decision_utc)
    observations=[]
    for snapshot in snapshots:
        verify_observation(snapshot)
        if _time(snapshot["observed_at_utc"])>cut:continue
        for row in snapshot["rows"]:
            if str(row["game_id"])==str(game_id) and row["team"]==team and (
                cut<_time(row["kickoff_utc"])):
                observations.append(row)
    if not observations:
        return {"status":"UNKNOWN","player":None,"reason":"NO_PREDECISION_OBSERVATION",
                "betting_status":"PASS_UNVALIDATED"}
    observations.sort(key=lambda r:_time(r["observed_at_utc"]))
    latest=observations[-1]
    verified={r["starter_player"] for r in observations
              if r["starter_status"]=="CONFIRMED_REVIEWED_PREKICKOFF"}
    status=latest["starter_status"]
    if len(verified)>1:
        status="CONFLICT_REQUIRES_REVIEW"
    # No starter carryover: latest UNKNOWN remains UNKNOWN even if an older
    # report confirmed someone. Contradictory reports require human review.
    return {"status":status,
            "player":latest["starter_player"] if status=="CONFIRMED_REVIEWED_PREKICKOFF" else None,
            "asof_utc":latest["observed_at_utc"],
            "observations_considered":len(observations),
            "reason":"GAME_SPECIFIC_REVIEW_ONLY",
            "betting_status":"PASS_UNVALIDATED"}

def run(context_path,queue_path,out_path,now=None):
    context=json.loads(Path(context_path).read_text())
    queue=json.loads(Path(queue_path).read_text())
    observed=_time(now or dt.datetime.now(dt.timezone.utc).isoformat())
    result=observe(context,queue,observed)
    verify_observation(result)
    output=Path(out_path);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as f:
        f.write(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result["summary"]))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--context",required=True)
    p.add_argument("--queue",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    run(a.context,a.queue,a.output)
