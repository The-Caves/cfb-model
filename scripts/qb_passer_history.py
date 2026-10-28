"""Research-only quarterback-attributed pass-play history from accepted 2026 PBP.

An observed passer, even the most-used passer, is NOT a verified starter.
Source play-by-play can be retroactively revised; first observed publication
is today's data retrieval, not the historical pregame publication instant.
"""
import datetime as dt
import math
from collections import Counter

STATUS="QB_PBP_POSTGAME_PASSER_ATTRIBUTION_RESEARCH_ONLY"
FIELDS=("game_id","date","team","opponent","player","pass_tagged_plays",
        "pass_epa_plays","pass_epa_sum","team_pass_tagged_plays",
        "team_named_passer_plays","team_unnamed_passer_plays",
        "pass_play_share","passer_identity_status",
        "source_retrieved_at_utc","historical_source_time_verified","betting_status")

def _epa(play):
    for name in ("EPA","EPA_scrimmage"):
        val=play.get(name)
        if val in ("",None):continue
        try:x=float(val)
        except (ValueError,TypeError):continue
        if math.isfinite(x) and -40<=x<=40:return x
    return None

def collect(game,team,opponent,accepted_offensive,observed_at):
    """Only call on score-matched, two-sided accepted completed PBP games.

    Returns player rows plus evidence coverage. Untagged/unnamed pass plays
    remain UNKNOWN, not silently awarded to the team's leading passer.
    """
    at=dt.datetime.fromisoformat(observed_at.replace("Z","+00:00"))
    if at.tzinfo is None:raise ValueError("Unzoned source observation")
    day=dt.date.fromisoformat(game["date"])
    if day>=at.date() or not team or not opponent or team==opponent:
        raise ValueError("QB ledger cannot contain present/future football outcome")
    by_player={}
    total=0;missing=0
    for p in accepted_offensive:
        if p.get("_pass") is not True:continue
        total+=1
        raw=p.get("passer_player_name")
        name=" ".join(raw.split()) if isinstance(raw,str) else ""
        if not 2<=len(name)<=120:
            missing+=1
            continue
        norm=name.casefold()
        bucket=by_player.setdefault(norm,{"name":name,"plays":0,"epa_plays":0,"epa":0.})
        bucket["plays"]+=1
        epa=_epa(p)
        if epa is not None:
            bucket["epa_plays"]+=1
            bucket["epa"]+=epa
    named=total-missing
    if named!=sum(x["plays"] for x in by_player.values()):
        raise ValueError("QB player attribution does not reconcile to pass plays")
    rows=[]
    for item in sorted(by_player.values(),key=lambda x:(-x["plays"],x["name"].casefold())):
        rows.append({"game_id":str(game["game_id"]),"date":game["date"],
            "team":team,"opponent":opponent,"player":item["name"],
            "pass_tagged_plays":item["plays"],"pass_epa_plays":item["epa_plays"],
            "pass_epa_sum":round(item["epa"],8),
            "team_pass_tagged_plays":total,"team_named_passer_plays":named,
            "team_unnamed_passer_plays":missing,
            "pass_play_share":round(item["plays"]/total,6) if total else 0.,
            "passer_identity_status":"POSTGAME_PASSER_NOT_STARTER_VERIFIED",
            "source_retrieved_at_utc":at.isoformat(),
            "historical_source_time_verified":False,
            "betting_status":"PASS_UNVALIDATED"})
    qa={"game_id":str(game["game_id"]),"team":team,"pass_tagged_plays":total,
        "named_pass_tagged_plays":named,"unnamed_pass_tagged_plays":missing,
        "unique_named_passers":len(rows),
        "leading_pass_share":rows[0]["pass_play_share"] if rows else None,
        "named_coverage":round(named/total,6) if total else None,
        "starter_verified":False}
    return rows,qa

def _numeric(row,key):
    try:
        v=float(row[key])
        if not math.isfinite(v):raise ValueError()
        return v
    except (ValueError,TypeError,KeyError):
        raise ValueError("Malformed QB passer history: "+key)

def prior_qb_form(rows,team,player,game_date,asof_utc,minimum_pass_plays=15):
    """Player-conditioned prior-game metrics, not a causal point adjustment.

    A reported expected QB requires external, timestamp-safe pregame evidence.
    This function describes prior pass plays ONLY. No same-day/future games or
    post-decision source observations enter the feature.
    """
    cutoff=dt.date.fromisoformat(game_date)
    observed=dt.datetime.fromisoformat(asof_utc.replace("Z","+00:00"))
    if observed.tzinfo is None or observed.date()>cutoff:
        raise ValueError("QB source observed later than the target football date")
    wanted=" ".join(player.split()).casefold() if isinstance(player,str) else ""
    if len(wanted)<2:raise ValueError("Expected QB name is required")
    related=[]
    ids=set()
    for row in rows:
        if row.get("team")!=team:continue
        date=dt.date.fromisoformat(row["date"])
        if date>=cutoff:
            # Historical ledger can contain newer games; exclude, not impute.
            continue
        retrieved=dt.datetime.fromisoformat(
            row["source_retrieved_at_utc"].replace("Z","+00:00"))
        if retrieved.tzinfo is None:raise ValueError("Unzoned source receipt")
        if retrieved>observed:continue
        provenance=row.get("historical_source_time_verified")
        if (row.get("betting_status")!="PASS_UNVALIDATED" or
            provenance not in (False,"False","false")):
            raise ValueError("Untrusted historical player source")
        key=(row["game_id"]," ".join(row["player"].split()).casefold())
        if key in ids:raise ValueError("Duplicate team/game/QB attribution")
        ids.add(key)
        related.append(row)
    player_rows=[r for r in related if " ".join(r["player"].split()).casefold()==wanted]
    other=[r for r in related if " ".join(r["player"].split()).casefold()!=wanted]
    def rate(subset):
        n=sum(_numeric(r,"pass_epa_plays") for r in subset)
        if n<minimum_pass_plays:return None
        return sum(_numeric(r,"pass_epa_sum") for r in subset)/n
    player_epa=rate(player_rows);other_epa=rate(other)
    plays=sum(_numeric(r,"pass_tagged_plays") for r in player_rows)
    other_plays=sum(_numeric(r,"pass_tagged_plays") for r in other)
    return {"team":team,"player":player,"asof_utc":observed.isoformat(),
        "prior_player_games":len({r["game_id"] for r in player_rows}),
        "prior_player_pass_tagged_plays":int(plays),
        "prior_other_qb_pass_tagged_plays":int(other_plays),
        "player_epa_per_pass_tagged_play":round(player_epa,6) if player_epa is not None else None,
        "other_qb_epa_per_pass_tagged_play":round(other_epa,6) if other_epa is not None else None,
        "within_team_player_minus_other_epa":round(player_epa-other_epa,6)
            if player_epa is not None and other_epa is not None else None,
        "qb_point_adjustment":None,
        "participation_not_proof_of_starting":True,
        "source_historical_publication_verified":False,
        "status":"QB_CONDITIONAL_HISTORY_RESEARCH_ONLY"}
