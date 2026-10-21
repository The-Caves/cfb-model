"""Strict as-of ingestion for sourced college-football player-availability signals.

A missing report never means 'healthy'. Records require timestamps and human
review attribution. We never assume that every conference publishes reports.
"""
import csv,datetime as dt
from pathlib import Path
from scripts.game_context import parse_time

POSITIONS={"QB","RB","WR","TE","OL","DL","EDGE","LB","CB","DB","S","K","P","OTHER","TEAM"}
STATUSES={"AVAILABLE","PROBABLE","QUESTIONABLE","DOUBTFUL","OUT","SUSPENDED",
          "LIMITED","GAME_TIME_DECISION","UNKNOWN","CONFIRMED","VERIFIED"}
KINDS={"INJURY","AVAILABILITY","QB_STARTER","TEAM_REPORT"}
FIELDS=["season","game_id","team","kind","player","position","status",
        "kickoff_utc","published_at_utc","captured_at_utc","source_url","reviewed_by"]

def load_reports(path):
    if path is None:return []
    with Path(path).open(newline="",encoding="utf-8-sig") as f:
        r=csv.DictReader(f)
        if not set(FIELDS).issubset(set(r.fieldnames or [])):
            raise ValueError("Availability report missing required columns")
        return list(r)

def evaluate(game,issue,records,attestation_age_hours=30):
    issued=parse_time(issue) if isinstance(issue,str) else issue
    kickoff=parse_time(game["kickoff_utc"])
    teams=(game["home"],game["away"])
    issues=[];valid=[]
    if issued>=kickoff:raise ValueError("Pregame issue time must precede kickoff")
    for idx,r in enumerate(records):
        if r.get("game_id")!=game["game_id"]:continue
        if r.get("season")!="2026" or r.get("team") not in teams:
            issues.append("record "+str(idx)+": wrong season or team");continue
        kind=r.get("kind")
        if kind not in KINDS or r.get("position") not in POSITIONS or r.get("status") not in STATUSES:
            issues.append("record "+str(idx)+": bad kind, position or status");continue
        if not r.get("player","").strip() or not r.get("source_url","").startswith("https://"):
            issues.append("record "+str(idx)+": unsourced player status");continue
        if not r.get("reviewed_by","").strip():
            issues.append("record "+str(idx)+": unreviewed source");continue
        try:
            pub=parse_time(r["published_at_utc"])
            capture=parse_time(r["captured_at_utc"])
            listed=parse_time(r["kickoff_utc"])
        except (TypeError,KeyError,ValueError):
            issues.append("record "+str(idx)+": invalid timestamp");continue
        if listed!=kickoff or not pub<=capture<=issued<kickoff:
            issues.append("record "+str(idx)+": post-cutoff, before-published, or kickoff mismatch");continue
        if kind=="TEAM_REPORT" and not (
           r["player"]=="ALL" and r["position"]=="TEAM" and r["status"]=="VERIFIED"):
            issues.append("record "+str(idx)+": invalid team-wide attestation");continue
        if kind=="QB_STARTER" and not (
           r["position"]=="QB" and r["status"]=="CONFIRMED"
           and r.get("evidence_scope")=="EXPLICIT_THIS_GAME"
           and r.get("source_type") in ("OFFICIAL_TEAM_RELEASE","ON_RECORD_COACH_CONFIRMATION")
           and r.get("review_status")=="APPROVED"
           and r.get("opponent")== (game["away"] if r["team"]==game["home"] else game["home"])
           and (r.get("evidence_excerpt") or "").strip()
           and (r.get("reviewed_at_utc") or "").strip()):
            issues.append("record "+str(idx)+": QB source not explicitly game-reviewed");continue
        if kind=="QB_STARTER":
            try: reviewer_time=parse_time(r["reviewed_at_utc"])
            except (ValueError,TypeError):
                issues.append("record "+str(idx)+": bad QB review timestamp");continue
            if not capture<=reviewer_time<=issued:
                issues.append("record "+str(idx)+": QB review outside as-of window");continue
        if kind in ("INJURY","AVAILABILITY") and r["status"] in ("CONFIRMED","VERIFIED"):
            issues.append("record "+str(idx)+": incompatible injury status");continue
        valid.append({**r,"_published":pub,"_captured":capture})
    coverage={};injuries=[];starters={}
    for team in teams:
        attest=[r for r in valid if r["team"]==team and r["kind"]=="TEAM_REPORT"
                and (issued-r["_captured"]).total_seconds()<=attestation_age_hours*3600]
        coverage[team]="VERIFIED_REPORT_REVIEWED" if attest else "UNKNOWN"
        injury_by_player={}
        for r in valid:
            if r["team"]==team and r["kind"] in ("INJURY","AVAILABILITY"):
                before=injury_by_player.get(r["player"])
                if before is None or (r["_captured"],r["_published"])>(before["_captured"],before["_published"]):
                    injury_by_player[r["player"]]=r
        injuries.extend({"team":team,"player":r["player"],"position":r["position"],"signal_kind":r["kind"],
                         "status":r["status"],"published_at_utc":r["published_at_utc"],
                         "captured_at_utc":r["captured_at_utc"],"source_url":r["source_url"]}
                        for r in injury_by_player.values())
        qbs=[r for r in valid if r["team"]==team and r["kind"]=="QB_STARTER"]
        if qbs:
            latest=max(r["_captured"] for r in qbs)
            candidates={r["player"] for r in qbs if r["_captured"]==latest}
            # Contradictions from any accepted source must not be silently
            # promoted into a confirmed starter, regardless of capture order.
            all_names={r["player"].casefold() for r in qbs}
            conflict_statuses={"OUT","SUSPENDED","DOUBTFUL","LIMITED"}
            unavailable={r["player"].casefold():r["status"] for r in injury_by_player.values()
                         if r["position"]=="QB" and r["status"] in conflict_statuses}
            if len(all_names)>1:
                issues.append(team+": conflicting QB-starter claims")
            elif any(qb in unavailable for qb in all_names):
                issues.append(team+": starter claim conflicts with latest official QB availability")
            elif len(candidates)==1:
                q=next(r for r in qbs if r["_captured"]==latest)
                starters[team]={"player":q["player"],"published_at_utc":q["published_at_utc"],
                                "captured_at_utc":q["captured_at_utc"],"source_url":q["source_url"],
                                "evidence_scope":q["evidence_scope"],"source_type":q["source_type"],
                                "reviewed_at_utc":q["reviewed_at_utc"]}
            else:
                issues.append(team+": conflicting QB-starter claims")
    both=all(coverage[t]=="VERIFIED_REPORT_REVIEWED" for t in teams)
    return {"coverage_status":"BOTH_TEAMS_VERIFIED" if both else
               "PARTIAL" if any(x=="VERIFIED_REPORT_REVIEWED" for x in coverage.values()) else "UNKNOWN",
            "coverage_by_team":coverage,"confirmed_qb_starters":starters,
            "injuries":injuries,"warnings":issues+(
              [] if both else ["At least one team lacks a complete, fresh reviewed availability report"]),
            "source_records_accepted":len(valid),"source_records_rejected":len(issues),
            "betting_status":"PASS_UNVALIDATED"}
