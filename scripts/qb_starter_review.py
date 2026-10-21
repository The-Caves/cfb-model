"""Game-specific, explicitly reviewed starting-quarterback evidence.

This does NOT discover starters automatically. A dated official team statement
and an independent human audit are needed before a QB_STARTER claim is emitted.
Candidate articles, media projections, charts, and availability alone do not
constitute this evidence. All unavailable assertions stay UNKNOWN.
"""
import csv
import re
from pathlib import Path
from urllib.parse import urlsplit
from scripts.game_context import parse_time

EVIDENCE_FIELDS = (
    "season","game_id","team","opponent","player","kickoff_utc",
    "published_at_utc","captured_at_utc","reviewed_at_utc","source_url",
    "source_type","evidence_scope","evidence_excerpt","review_status","reviewed_by"
)
SOURCE_TYPES = {"OFFICIAL_TEAM_RELEASE", "ON_RECORD_COACH_CONFIRMATION"}
EVIDENCE_SCOPE = "EXPLICIT_THIS_GAME"
# Mechanical screening is conservative and is NOT semantic source verification.
# Require affirmative starting language; a bare word "start" also appears in
# negative or speculative statements ("will not start", "could start").
AFFIRMATIVE_START = re.compile(
    r"\b(will start|is starting|will be starting|named (?:the )?starter|"
    r"has been named (?:the )?starter|starting quarterback|"
    r"start at quarterback|starting at quarterback)\b", re.I)
NEGATED_OR_UNCERTAIN = re.compile(
    r"\b(?:will not|won't|is not|isn't|cannot|can't|could|may|might|"
    r"not expected to|unlikely to|projected to|expected to|likely to|"
    r"no decision on|has not been named)\s+"
    r"(?:(?:\w+|the)\s+){0,4}(?:start|starting|starter)\b", re.I)

def load_reviewed_qb_starters(path, games, issue):
    """Return safe QB_STARTER claims plus an auditable, non-sensitive manifest.

    No network call is made. The reviewer, not this function, is responsible
    for verifying that an official source genuinely says what its excerpt does.
    """
    qa={"status":"NO_SUBMITTED_QB_EVIDENCE","submitted":0,"accepted":0,
        "rejected":0,"reasons":[],"confirmed_game_team_slots":0}
    if path is None:
        return [],qa
    with Path(path).open(newline="",encoding="utf-8-sig") as handle:
        rdr=csv.DictReader(handle)
        if not set(EVIDENCE_FIELDS).issubset(rdr.fieldnames or []):
            raise ValueError("QB evidence CSV missing required fields")
        rows=list(rdr)
    qa["submitted"]=len(rows)
    now=parse_time(issue)
    game_map={str(g["game_id"]):g for g in games}
    if len(game_map)!=len(games):
        raise ValueError("Duplicate ESPN game IDs in QB evidence slate")
    good=[]
    for ix,row in enumerate(rows,1):
        reason=None
        game=game_map.get(row.get("game_id"))
        team=(row.get("team") or "").strip()
        player=(row.get("player") or "").strip()
        opponent=(row.get("opponent") or "").strip()
        excerpt=(row.get("evidence_excerpt") or "").strip()
        source_url=(row.get("source_url") or "").strip()
        try:
            kickoff=parse_time(row["kickoff_utc"])
            published=parse_time(row["published_at_utc"])
            captured=parse_time(row["captured_at_utc"])
            reviewed=parse_time(row["reviewed_at_utc"])
        except (KeyError,TypeError,ValueError):
            reason="BAD_TIMESTAMPS"
        if not reason and (game is None or row.get("season")!="2026"):
            reason="UNKNOWN_GAME_OR_SEASON"
        if not reason and (kickoff!=parse_time(game["kickoff_utc"])
                           or team not in (game["home"],game["away"])
                           or opponent != (game["away"] if team==game["home"] else game["home"])):
            reason="GAME_TEAM_OPPONENT_MISMATCH"
        if not reason and not (published<=captured<=reviewed<=now<kickoff):
            reason="PRE_KICKOFF_CUTOFF_VIOLATION"
        if not reason and (kickoff-published).total_seconds()>14*86400:
            reason="NOT_GAME_WEEK_EVIDENCE"
        if not reason and (row.get("source_type") not in SOURCE_TYPES
                           or row.get("evidence_scope")!=EVIDENCE_SCOPE
                           or row.get("review_status")!="APPROVED"
                           or not (row.get("reviewed_by") or "").strip()):
            reason="NOT_EXPLICIT_APPROVED_EVIDENCE"
        if not reason:
            parsed_url=urlsplit(source_url)
            if parsed_url.scheme!="https" or not parsed_url.hostname or parsed_url.username or parsed_url.password:
                reason="INVALID_PUBLIC_SOURCE_URL"
        if not reason and (not 3<=len(player)<=100 or len(excerpt)>700
                           or player.casefold() not in excerpt.casefold()
                           or not AFFIRMATIVE_START.search(excerpt)
                           or NEGATED_OR_UNCERTAIN.search(excerpt)):
            reason="NO_EXPLICIT_PLAYER_START_STATEMENT"
        if reason:
            qa["reasons"].append({"row":ix,"game_id":row.get("game_id"),"reason":reason})
            continue
        good.append((ix,{
            "season":"2026","game_id":str(game["game_id"]),"team":team,
            "kind":"QB_STARTER","player":player,"position":"QB","status":"CONFIRMED",
            "kickoff_utc":game["kickoff_utc"],
            "published_at_utc":row["published_at_utc"],
            "captured_at_utc":row["captured_at_utc"],
            "reviewed_at_utc":row["reviewed_at_utc"],
            "source_url":source_url,"source_type":row["source_type"],
            "evidence_scope":EVIDENCE_SCOPE,"evidence_excerpt":excerpt,
            "opponent":opponent,"review_status":"APPROVED",
            "reviewed_by":row["reviewed_by"]
        }))
    # A stale and a new competing claim both need review; never silently pick
    # the latest of contradictory quarterback statements.
    groups={}
    for ix,r in good:
        groups.setdefault((r["game_id"],r["team"]),[]).append((ix,r))
    claims=[]
    for key,entries in groups.items():
        if len({r["player"].casefold() for _,r in entries})>1:
            for ix,_ in entries:
                qa["reasons"].append({"row":ix,"game_id":key[0],
                                      "reason":"CONFLICTING_STARTER_CLAIMS"})
            continue
        claims.append(max((r for _,r in entries),
                          key=lambda r:parse_time(r["reviewed_at_utc"])))
    qa["accepted"]=len(claims)
    qa["rejected"]=qa["submitted"]-qa["accepted"]
    qa["confirmed_game_team_slots"]=len(claims)
    qa["status"]="REVIEWED_QB_EVIDENCE_ACCEPTED" if claims else (
        "NO_SUBMITTED_QB_EVIDENCE" if not rows else "NO_ACCEPTABLE_QB_EVIDENCE")
    return claims,qa
