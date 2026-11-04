"""Explicit university-issued 2026 long-term QB OUT facts for future games only.

This is reviewed source evidence, NOT an inferred QB1 starter, a player-value
estimate, or permission to rewrite a previously published forecast.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlsplit
from scripts.game_context import parse_time

STATUS="REVIEWED_OFFICIAL_LONGTERM_QB_ABSENCE_2026_V1"
AUDIT="FUTURE_ONLY_OFFICIAL_QB_OUT_REPLACEMENT_UNMEASURED"
ALLOWED={"OUT_REMAINDER_2026"}


def apply(board,registry,now):
    when=parse_time(now)
    if (board.get("schema_version")!=2 or
        board.get("betting_status")!="PASS_UNVALIDATED" or
        registry.get("status")!=STATUS or registry.get("season")!=2026 or
        not isinstance(registry.get("records"),list)):
        raise ValueError("Unverified official QB absence input")
    index={}
    for rec in registry["records"]:
        if (not isinstance(rec,dict) or rec.get("human_reviewed") is not True or
            rec.get("source_type")!="OFFICIAL_UNIVERSITY_STATEMENT" or
            rec.get("position")!="QB" or rec.get("designation") not in ALLOWED or
            not isinstance(rec.get("team"),str) or
            not isinstance(rec.get("player"),str) or
            not 4<=len(rec["player"])<=100):
            raise ValueError("Unreviewed QB outage record")
        url=urlsplit(rec.get("source_url",""))
        if (url.scheme!="https" or url.hostname!=rec.get("publisher_host") or
            url.username or url.password or url.fragment or
            url.port not in (None,443) or not url.path.startswith("/news/2026/")):
            raise ValueError("Official QB source not trusted")
        pub=dt.date.fromisoformat(rec["published_date"])
        eligible=parse_time(rec["first_eligible_at_utc"])
        if pub.year!=2026 or eligible.date()<pub or (
             eligible-dt.datetime.combine(pub,dt.time.min,tzinfo=dt.timezone.utc)
             ).total_seconds()<3600:
            raise ValueError("QB outage first-use timestamp predates source")
        key=(rec["team"]," ".join(rec["player"].casefold().split()))
        if key in index:
            raise ValueError("Multiple conflicting QB records for school and player")
        index[key]=(rec,eligible)
    known=set()
    applied=0
    blocked=0
    for game in board["games"]:
        gid=str(game["game_id"])
        if gid in known:raise ValueError("Duplicate fixture in QB outage overlay")
        known.add(gid)
        kickoff=parse_time(game["kickoff_utc"])
        for side in ("home","away"):
            key="official_longterm_qb_absence_"+side
            game[key]=None
            game["official_longterm_qb_absences_"+side]=[]
            team=game[side+"_team"]
            if not when<kickoff or kickoff.year!=2026:continue
            eligible_records=sorted(
                (rec for (school,_), (rec,first) in index.items()
                 if school==team and first<=when),
                key=lambda rec:rec["player"].casefold())
            if not eligible_records:continue
            qb=game.get("qb_"+side) or {}
            claimed=str(qb.get("player") or "").casefold()
            out_names={rec["player"].casefold() for rec in eligible_records}
            confirmed=bool(qb.get("status")=="CONFIRMED_OFFICIAL" and
                           claimed and claimed not in out_names)
            # A claimed confirmed starter who is officially season-OUT is a
            # contradiction requiring review, not a usable replacement.
            if qb.get("status")=="CONFIRMED_OFFICIAL" and claimed in out_names:
                game["qb_"+side]={**qb,"status":"CONFLICT_REVIEW",
                    "description":"Reviewed season-ending QB absence contradicts starter claim"}
            for record in eligible_records:
                outage={
                    "status":"OFFICIAL_SEASON_OUT_VERIFIED_AFTER_SOURCE_REVIEW",
                    "player":record["player"],"position":"QB",
                    "source_url":record["source_url"],
                    "published_date":record["published_date"],
                    "first_eligible_at_utc":record["first_eligible_at_utc"],
                    "designation":record["designation"],
                    "verified_replacement_starter":confirmed,
                    "replacement_value_calibrated":False,
                    "changes_frozen_score":False,
                    "source_type":record["source_type"]}
                game["official_longterm_qb_absences_"+side].append(outage)
            # Backward compatibility with existing V04 research PASS gate.
            game[key]=game["official_longterm_qb_absences_"+side][0]
            applied+=1
            blocked+=int(not confirmed)
    board["official_longterm_qb_absence_audit"]={
        "status":AUDIT,"reviewed_records":len(index),
        "future_team_sides_with_verified_longterm_absence":applied,
        "reviewed_unavailable_qb_players":len(index),
        "active_future_outage_player_records":sum(
            len(g.get("official_longterm_qb_absences_"+side,[]))
            for g in board["games"] for side in ("home","away")),
        "team_sides_without_verified_replacement":blocked,
        "score_predictions_unchanged":True,
        "outage_does_not_imply_starter_confirmation":True,
        "historical_pre_source_forecasts_rewritten":False,
        "no_arbitrary_injury_point_deduction":True}
    return board


def run(dashboard,registry,now=None):
    when=now or dt.datetime.now(dt.timezone.utc).isoformat()
    path=Path(dashboard)
    board=json.loads(path.read_text(encoding="utf-8"))
    info=json.loads(Path(registry).read_text(encoding="utf-8"))
    result=apply(board,info,when)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(result["official_longterm_qb_absence_audit"],sort_keys=True))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--dashboard",required=True)
    p.add_argument("--registry",required=True)
    args=p.parse_args()
    run(args.dashboard,args.registry)
