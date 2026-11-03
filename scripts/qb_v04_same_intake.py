"""Freeze an independent V04 score control from the SAME source intake as QB.

This result is computed and written BEFORE the QB shadow exists, using only
already-observed completed scores and the source-matched future fixture board.
It is NOT an earlier published website projection, and no line is used.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

from scripts.game_context import parse_time
from scripts.site_home_bias_guard import _previous_football_day_rows
from scripts.v04_direct_scores import fit,predict,MODEL,STATUS as V04_STATUS
from scripts.personnel_forecast import checksum

STATUS="V04_SAME_INTAKE_FROZEN_BEFORE_QB_SHADOW_RESEARCH_ONLY"


def build(context,rows,manifest,issued_utc,raw_scores_sha256,raw_manifest_sha256):
    issued=parse_time(issued_utc)
    source=parse_time(manifest["retrieved_at_utc"])
    context_time=parse_time(context["captured_at_utc"])
    if (manifest.get("status")!="SUCCESS" or manifest.get("failures") or
        manifest.get("requested_start")!="2026-08-01" or
        manifest.get("scoreboard_date_timezone")!="America/New_York" or
        not source<=context_time<=issued or
        (issued-context_time).total_seconds()>45*60 or
        context.get("season",2026)!=2026):
        raise ValueError("Late or untrusted same-intake V04 scores/fixture context")
    for digest in (raw_scores_sha256,raw_manifest_sha256):
        if not isinstance(digest,str) or len(digest)!=64:
            raise ValueError("Unbound V04 source byte digest")
    prior,embargoed=_previous_football_day_rows(rows,issued)
    model=fit(prior,issued.isoformat())
    if (model["model"]!=MODEL or model["status"]!=V04_STATUS or
        model["market_used_for_fit"] is not False or
        model["model_promoted"] is not False or
        model["n_training_games"]!=len(prior)):
        raise ValueError("Untrusted direct V04 scoring fit")
    games=[];seen=set()
    for g in context["games"]:
        if parse_time(g["kickoff_utc"])<=issued:
            continue
        gid=str(g["game_id"])
        if gid in seen:raise ValueError("Repeated future game in V04 source context")
        seen.add(gid)
        if (not g["home"] or not g["away"] or g["home"]==g["away"]
            or type(g.get("neutral")) is not bool):
            raise ValueError("Invalid official future fixture for V04")
        score=predict(model,g["home"],g["away"],g["neutral"])
        games.append({"game_id":gid,"home":g["home"],"away":g["away"],
            "kickoff_utc":g["kickoff_utc"],"neutral":g["neutral"],
            "v04_direct_score":score})
    if not games:raise ValueError("No valid next-game V04 cohort")
    return {
        "status":STATUS,"model":MODEL,"season":2026,
        "observed_at_utc":issued.isoformat(),
        "score_source_retrieved_at_utc":source.isoformat(),
        "fixture_source_captured_at_utc":context_time.isoformat(),
        "scoreboard_csv_sha256":raw_scores_sha256,
        "scoreboard_manifest_sha256":raw_manifest_sha256,
        "fixture_context_sha256":checksum(context),
        "training_score_rows_sha256":checksum(prior),
        "source_training_games":len(prior),
        "same_day_completed_scores_embargoed":embargoed,
        "training_source_first_publication_authenticated":False,
        "direct_score_fit_uses_v03":False,
        "market_used_for_fit":False,
        "summary":{"future_games":len(games),
                   "games_with_v04":sum(x["v04_direct_score"] is not None for x in games)},
        "games":games,
        "safe_for_betting":False,
        "model_promoted":False,"betting_status":"PASS_UNVALIDATED"}


def attach(qb,control):
    """Bind already-frozen same-intake V04 receipts before archiving QB."""
    if (qb.get("model_promoted") is not False or
        qb.get("betting_status")!="PASS_UNVALIDATED" or
        control.get("status")!=STATUS or
        control.get("model")!=MODEL or
        control.get("direct_score_fit_uses_v03") is not False or
        control.get("market_used_for_fit") is not False or
        control.get("model_promoted") is not False):
        raise ValueError("Invalid QB/V04 research binding")
    issued=parse_time(qb["observed_at_utc"])
    control_at=parse_time(control["observed_at_utc"])
    scores_at=parse_time(control["score_source_retrieved_at_utc"])
    fixture_at=parse_time(control["fixture_source_captured_at_utc"])
    if not scores_at<=fixture_at<=control_at<=issued:
        raise ValueError("V04 score source observed after QB forecast")
    lookup={str(r["game_id"]):r for r in control["games"]}
    if len(lookup)!=len(control["games"]):raise ValueError("Repeated V04 source game")
    if len({str(r["game_id"]) for r in qb["games"]})!=len(qb["games"]):
        raise ValueError("Repeated QB scenario game")
    source_sha=checksum(control)
    for q in qb["games"]:
        gid=str(q["game_id"])
        z=lookup.get(gid)
        if z is None:raise ValueError("No same-intake V04 forecast for QB scenario")
        if (q["home"]!=z["home"] or q["away"]!=z["away"] or
            parse_time(q["kickoff_utc"])!=parse_time(z["kickoff_utc"]) or
            parse_time(q["kickoff_utc"])<=issued):
            raise ValueError("Same-intake V04 game/clock changed")
        prediction=z["v04_direct_score"]
        if prediction is not None:
            if (prediction.get("status")!=V04_STATUS or prediction.get("model")!=MODEL or
                prediction.get("direct_scoring_fit_uses_v03_total") is not False or
                prediction.get("no_market_lines_in_training") is not True or
                prediction.get("model_promoted") is not False or
                prediction.get("source_training_games")!=control["source_training_games"]):
                raise ValueError("Untrusted same-intake V04 model receipt")
        q["same_intake_v04"]={
            "source_class":STATUS,
            "source_bundle_sha256":source_sha,
            "source_observed_at_utc":control_at.isoformat(),
            "source_score_retrieved_at_utc":scores_at.isoformat(),
            "source_fixture_observed_at_utc":fixture_at.isoformat(),
            "source_scoreboard_sha256":control["scoreboard_csv_sha256"],
            "source_manifest_sha256":control["scoreboard_manifest_sha256"],
            "source_training_rows_sha256":control["training_score_rows_sha256"],
            "source_context_sha256":control["fixture_context_sha256"],
            "home_margin":prediction["home_margin"] if prediction else None,
            "total_points":prediction["total_points"] if prediction else None,
            "status":prediction["status"] if prediction else "V04_TEAM_NOT_IN_PRIOR_HISTORY",
            "model":MODEL,
            "market_used_for_fit":False,
            "no_v03_scores_used":True,
            "before_qb_shadow_issued":True,
            "not_a_published_website_snapshot":True,
            "model_promoted":False}
    qb["same_intake_v04_source_sha256"]=source_sha
    qb["same_intake_v04_source_observed_at_utc"]=control_at.isoformat()
    qb["summary"]["same_intake_v04_game_scores"]=sum(
        r["same_intake_v04"]["home_margin"] is not None for r in qb["games"])
    return qb

def run(context_file,games_csv,manifest_file,output):
    with open(games_csv,newline="",encoding="utf-8") as handle:
        rows=list(csv.DictReader(handle))
    manifest_bytes=Path(manifest_file).read_bytes()
    context=json.loads(Path(context_file).read_text(encoding="utf-8"))
    manifest=json.loads(manifest_bytes)
    result=build(context,rows,manifest,dt.datetime.now(dt.timezone.utc).isoformat(),
                 hashlib.sha256(Path(games_csv).read_bytes()).hexdigest(),
                 hashlib.sha256(manifest_bytes).hexdigest())
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2,allow_nan=False);f.write("\n")
    print(json.dumps({"status":STATUS,**result["summary"],
                      "model_promoted":False,"betting_status":"PASS_UNVALIDATED"}))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    for field in ("context","games","manifest","output"):
        p.add_argument("--"+field,required=True)
    a=p.parse_args()
    run(a.context,a.games,a.manifest,a.output)
