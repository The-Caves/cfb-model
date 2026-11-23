"""Strict point-in-time evidence gate for future V12 player/weather research.

Historical artifacts collected after an old kickoff cannot be presented as if
available to the original forecast. This module records verified inputs but
does not invent QB, injury or weather impact coefficients. Unsupported rows
are excluded; unknown stays unknown.
"""
import datetime as dt
from urllib.parse import urlsplit

STATUS="V12_AUTHENTIC_POINT_IN_TIME_CONTEXT_RESEARCH_ONLY"
CATEGORIES=("qb","injury","weather")
VERIFIERS=("OFFICIAL_PRIMARY","AUTHENTIC_TIMESTAMPED_ARCHIVE")


def _time(value):
    if not isinstance(value,str) or not value:return None
    try:stamp=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:return None
    if stamp.tzinfo is None:return None
    return stamp.astimezone(dt.timezone.utc)


def snapshot(rows,*,game_id,home,away,asof_utc):
    """Only prior-observed, prior-published authentic records may enter snapshot.

    asof_utc must be the genuinely archived forecast decision timestamp,
    never a game-day time inferred from hindsight. Weather requires a forecast,
    not postgame observed conditions. All fields are untrusted until checked.
    """
    cutoff=_time(asof_utc)
    if cutoff is None or not game_id or not home or not away or home==away:
        raise ValueError("V12 missing authentic timestamp or matchup identity")
    if not isinstance(rows,list):raise ValueError("Evidence rows must be a list")
    accepted={};reasons={}
    for row in rows:
        reason=None
        if not isinstance(row,dict):
            reason="MALFORMED"
        elif str(row.get("game_id"))!=str(game_id):
            reason="WRONG_MATCHUP"
        elif row.get("category") not in CATEGORIES:
            reason="UNSUPPORTED_CATEGORY"
        elif ((row["category"]=="weather" and row.get("team")!="GAME") or
              (row["category"]!="weather" and row.get("team") not in (home,away))):
            reason="WRONG_TEAM"
        elif row.get("verification") not in VERIFIERS:
            reason="NOT_AUTHENTICATED"
        elif not isinstance(row.get("value"),dict) or not row["value"]:
            reason="NO_VERIFIABLE_INFORMATION"
        elif not (isinstance(row.get("source_url"),str)
                  and urlsplit(row["source_url"]).scheme=="https"
                  and urlsplit(row["source_url"]).netloc):
            reason="NO_HTTPS_SOURCE"
        elif row.get("category")=="weather" and row.get("weather_type")!="FORECAST":
            reason="ACTUAL_WEATHER_IS_LEAKAGE"
        else:
            published=_time(row.get("source_published_at_utc"))
            observed=_time(row.get("first_observed_at_utc"))
            if published is None or observed is None:
                reason="MISSING_AUTHENTIC_SOURCE_TIME"
            elif published>cutoff or observed>cutoff:
                reason="AFTER_FORECAST_CUTOFF"
            elif observed<published:
                reason="OBSERVED_BEFORE_SOURCE_PUBLISHED"
            else:
                key=(row["category"],row["team"])
                stamp=(observed,published)
                if key not in accepted or stamp>accepted[key][0]:
                    accepted[key]=(stamp,row)
                elif stamp==accepted[key][0] and row["value"]!=accepted[key][1]["value"]:
                    raise ValueError("Contradictory source at same authenticated time")
        if reason:reasons[reason]=reasons.get(reason,0)+1
    output={c:{"home":None,"away":None} if c!="weather" else {"GAME":None}
            for c in CATEGORIES}
    for (category,team),(_,row) in accepted.items():
        output[category]["GAME" if category=="weather" else
                          "home" if team==home else "away"]={
            "value":row["value"],"source_url":row["source_url"],
            "source_published_at_utc":row["source_published_at_utc"],
            "first_observed_at_utc":row["first_observed_at_utc"],
            "verification":row["verification"]}
    return {"status":STATUS,"game_id":str(game_id),
            "teams":{"home":home,"away":away},"asof_utc":asof_utc,
            "accepted_record_keys":len(accepted),"rejected_records":reasons,
            "evidence":output,"source_cutoff_checked":True,
            "unavailable_remains_unknown":True,
            "score_effects_applied":False,"model_promoted":False}
