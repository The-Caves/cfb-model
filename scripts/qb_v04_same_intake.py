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
