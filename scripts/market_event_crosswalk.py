"""Conservative provider-event to ESPN game crosswalk. No fuzzy joins or odds predictions."""
import csv,re,unicodedata
from collections import defaultdict
from pathlib import Path
from scripts.game_context import parse_time

def norm(v):
    if not isinstance(v,str):return ""
    return re.sub("[^a-z0-9]","",unicodedata.normalize("NFKD",v).casefold())

def load_registry(path):
    with Path(path).open(newline="",encoding="utf-8-sig") as f:
        rows=list(csv.DictReader(f))
    if not rows or not {"archived_team","espn_display_name"}.issubset(rows[0]):
        raise ValueError("Invalid 2026 team registry")
    aliases={};conflicts=set()
    for r in rows:
        name=(r.get("espn_display_name") or "").strip()
        if not name:raise ValueError("Empty ESPN display name")
        for candidate in (r.get("archived_team"),name):
            k=norm(candidate)
            if not k:raise ValueError("Blank alias")
            if k in aliases and aliases[k]!=name:conflicts.add(k)
            else:aliases[k]=name
    for k in conflicts:aliases.pop(k,None)
    return aliases,conflicts

def crosswalk(quote_bundle,espn_context,aliases,conflicts=(),max_minutes=15):
    """Only exact registered team aliases, direction, kickoff and as-of snapshots."""
    if not 0<=max_minutes<=60:raise ValueError("Invalid kickoff tolerance")
    if quote_bundle.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Unexpected market clearance")
    espn_time=parse_time(espn_context["asof_utc"])
    games=espn_context.get("games")
    if not isinstance(games,list):raise ValueError("Missing ESPN games")
    bypair=defaultdict(list);used_ids=set()
    for g in games:
        gid=str(g["game_id"])
        if gid in used_ids:raise ValueError("Duplicate ESPN game id")
        used_ids.add(gid)
        h,a=norm(g.get("home")),norm(g.get("away"))
        if h in aliases and a in aliases:
            bypair[(aliases[h],aliases[a])].append(g)
    odds=defaultdict(list)
    for q in quote_bundle.get("quotes",[]):
        if not isinstance(q,dict):raise ValueError("Malformed quote")
        odds[str(q["provider_event_id"])].append(q)
    taken=set();joined=[];reasons=defaultdict(int)
    for eid,rows in sorted(odds.items()):
        first=rows[0]
        fp={(q.get("home_team_source"),q.get("away_team_source"),
             q.get("kickoff_utc")) for q in rows}
        reason=None;selected=None
        if len(fp)!=1:reason="CONTRADICTORY_PROVIDER_EVENT"
        else:
            h,a=norm(first.get("home_team_source")),norm(first.get("away_team_source"))
            if h not in aliases or a not in aliases or h in conflicts or a in conflicts:
                reason="UNKNOWN_OR_AMBIGUOUS_TEAM"
            else:
                home,away=aliases[h],aliases[a]
                def nearby(g):
                    return abs((parse_time(g["kickoff_utc"])-
                                parse_time(first["kickoff_utc"])).total_seconds())<=max_minutes*60
                candidates=[g for g in bypair.get((home,away),[]) if nearby(g)]
                if len(candidates)!=1:
                    if any(nearby(g) for g in bypair.get((away,home),[])):
                        reason="HOME_AWAY_REVERSED"
                    else:reason="AMBIGUOUS_ESPN_MATCH" if candidates else "NO_MATCHING_KICKOFF"
                else:
                    g=candidates[0]
                    if g.get("completed"):reason="COMPLETED_GAME_CONTEXT"
                    elif any(parse_time(q["observed_at_utc"])<espn_time for q in rows):
                        reason="ESPN_SNAPSHOT_LATER_THAN_ODDS"
                    elif any(parse_time(q["observed_at_utc"])>=parse_time(q["kickoff_utc"]) for q in rows):
                        reason="IN_PLAY_OR_POST_KICKOFF"
                    elif str(g["game_id"]) in taken:
                        reason="DUPLICATE_PROVIDER_EVENT_FOR_ESPN_GAME"
                    elif not g.get("home_id") or not g.get("away_id"):
                        reason="NO_ESPN_TEAM_IDENTIFIERS"
                    else:
                        selected=g;taken.add(str(g["game_id"]))
        reasons[reason or "MATCHED"]+=1
        for q in rows:
            item=dict(q)
            item.update(espn_game_id=str(selected["game_id"]) if selected else None,
                home_espn_team_id=str(selected["home_id"]) if selected else None,
                away_espn_team_id=str(selected["away_id"]) if selected else None,
                neutral_from_espn=selected.get("neutral") if selected else None,
                espn_context_asof_utc=espn_time.isoformat(),
                match_status="MATCHED_ASOF" if selected else "QUARANTINED",
                match_reject_reason=reason,betting_status="PASS_UNVALIDATED")
            joined.append(item)
    return {"quotes":joined,"source_rejected":quote_bundle.get("rejected",[]),
            "coverage":{"events":len(odds),"matched":reasons["MATCHED"],
                "quarantined":len(odds)-reasons["MATCHED"],"reasons":dict(reasons)},
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
