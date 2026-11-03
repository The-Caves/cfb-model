"""As-observed long-term QB absences constrain projected-starter scenarios.

A university-confirmed OUT QB cannot be retained as the projected current
starter. Never choose QB2 by depth-rank alone and NEVER claim a confirmed
replacement, QB effect, or historical pregame knowledge that was not observed.
"""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlsplit

from scripts.game_context import parse_time
from scripts.qb_expected_starters import STATUS as EXPECTED_STATUS
from scripts.qb_passer_history import player_key
from scripts.official_longterm_qb_absences import STATUS as OUT_STATUS

STATUS="QB_OFFICIAL_LONGTERM_OUT_EXPECTED_STARTER_FILTER_V1"


def apply(expected, registry, now):
    observed=parse_time(now)
    if (not isinstance(expected,dict) or
        expected.get("status")!=EXPECTED_STATUS or expected.get("season")!=2026 or
        expected.get("betting_status")!="PASS_UNVALIDATED" or
        expected.get("model_promoted") is not False or
        registry.get("status")!=OUT_STATUS or registry.get("season")!=2026):
        raise ValueError("Untrusted source for QB absence filtering")
    if parse_time(expected["observed_at_utc"])>observed:
        raise ValueError("QB expected source observed in future")
    original=expected["observed_at_utc"]
    records={}
    for source in registry.get("records",[]):
        if (source.get("designation")!="OUT_REMAINDER_2026" or
            source.get("position")!="QB" or source.get("human_reviewed") is not True or
            source.get("source_type")!="OFFICIAL_UNIVERSITY_STATEMENT" or
            not isinstance(source.get("team"),str) or
            not isinstance(source.get("player"),str)):
            raise ValueError("Unverified official long-term QB source")
        link=urlsplit(source.get("source_url",""))
        if (link.scheme!="https" or link.hostname!=source.get("publisher_host") or
            link.username or link.password or link.fragment or
            link.port not in (None,443) or not link.path.startswith("/news/2026/")):
            raise ValueError("Official quarterback source publisher mismatch")
        first=parse_time(source["first_eligible_at_utc"])
        pub=dt.date.fromisoformat(source["published_date"])
        if first.date()<pub or pub.year!=2026:
            raise ValueError("QB source embargo predates published statement")
        if source["team"] in records:
            raise ValueError("Duplicate or conflicting team QB source")
        records[source["team"]]=(source,first)
    result=copy.deepcopy(expected)
    seen=set()
    applied=0;not_starter=0;removed=0;confirmed_conflicts=0
    for row in result["games"]:
        key=(str(row["game_id"]),row["team"])
        kickoff=parse_time(row["kickoff_utc"])
        if key in seen:raise ValueError("Repeated expected QB game/team")
        seen.add(key)
        if kickoff<=observed:continue
        item=records.get(row["team"])
        if item is None or observed<item[1] or kickoff.year!=2026:continue
        source,first=item
        name=player_key(source["player"])
        starter=row.get("starter")
        if row.get("is_confirmed_starter") is True and starter and player_key(starter)==name:
            # Conflicting university facts need human resolution; never silently
            # replace an independently reviewed game-specific starter.
            confirmed_conflicts+=1
            raise ValueError("Confirmed starter contradicts season-ending QB OUT")
        before=len(row.get("scenarios",[]))
        row["scenarios"]=[s for s in row.get("scenarios",[])
                          if player_key(s.get("player") or "")!=name]
        removed+=before-len(row["scenarios"])
        if starter and player_key(starter)==name:
            if row.get("is_confirmed_starter") is True:
                raise ValueError("Cannot demote reviewed true starter")
            row["starter"]=None
            row["starter_status"]="UNKNOWN_OFFICIAL_SEASON_OUT_NO_VERIFIED_REPLACEMENT"
            row["confidence"]="UNKNOWN"
            row["reason"]="OFFICIAL_SEASON_OUT_EXCLUDES_PROJECTED_QB_NOT_A_QB2_CONFIRMATION"
            row["depth_rank"]=None
            row["depth_label"]="UNKNOWN"
            row["is_confirmed_starter"]=False
            not_starter+=1
        row["official_longterm_out_qb"]={
            "player":source["player"],"designation":source["designation"],
            "source_url":source["source_url"],
            "published_date":source["published_date"],
            "first_eligible_at_utc":source["first_eligible_at_utc"],
            "observed_at_utc":observed.isoformat(),
            "does_not_confirm_replacement":True,
            "does_not_change_score":True,
            "historical_source_available_at_previous_forecast":False}
        # The newly observed source cannot inherit the prior QB-slate timestamp.
        row["original_expected_starter_observed_at_utc"]=row["observed_at_utc"]
        row["observed_at_utc"]=observed.isoformat()
        applied+=1
    result["original_expected_starter_observed_at_utc"]=original
    result["observed_at_utc"]=observed.isoformat()
    result["summary"]["projected_or_confirmed_starters"]=sum(
        bool(r.get("starter")) for r in result["games"])
    result["summary"]["confirmed_starters"]=sum(
        r.get("is_confirmed_starter") is True for r in result["games"])
    result["summary"]["unknown_starters"]=sum(
        not r.get("starter") for r in result["games"])
    result["qb_longterm_out_audit"]={
        "status":STATUS,
        "official_future_team_slots_annotated":applied,
        "projected_out_qbs_changed_to_unknown":not_starter,
        "unavailable_qb_scenarios_removed":removed,
        "official_source_review_conflicts":confirmed_conflicts,
        "replacement_starter_inferred":False,
        "arbitrary_qb_point_penalty":False,
        "previous_pregame_forecasts_rewritten":False}
    return result


def run(expected_path,registry_path):
    path=Path(expected_path)
    expected=json.loads(path.read_text(encoding="utf-8"))
    registry=json.loads(Path(registry_path).read_text(encoding="utf-8"))
    updated=apply(expected,registry,dt.datetime.now(dt.timezone.utc).isoformat())
    path.write_text(json.dumps(updated,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(updated["qb_longterm_out_audit"],sort_keys=True))
    return updated


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--expected",required=True)
    ap.add_argument("--registry",required=True)
    a=ap.parse_args()
    run(a.expected,a.registry)
