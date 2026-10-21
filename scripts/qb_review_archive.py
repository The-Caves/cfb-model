"""Validate and close the public, unreviewed QB source queue before archiving."""
from scripts.game_context import parse_time
from scripts.qb_review_queue import summarize

FEED_STATES={"FETCHED","FETCH_FAILED","NOT_CONFIGURED","UNKNOWN_FETCH_STATUS"}

def close_qb_review(queue,context):
    if queue.get("status")!="QB_REVIEW_RESEARCH_ONLY" or queue.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("QB queue is not research-only")
    if queue.get("safe_for_betting") is not False:
        raise ValueError("Unsafe QB review queue")
    start=parse_time(context["collection_started_utc"])
    cutoff=parse_time(context["asof_utc"])
    capture=parse_time(queue["asof_utc"])
    if not start<=capture<=cutoff:
        raise ValueError("QB queue outside context collection window")
    games={str(g["game_id"]):g for g in context["games"]}
    if len(games)!=len(context["games"]):
        raise ValueError("Duplicate game ID in context")
    accepted=[]
    seen=set()
    for row in queue.get("rows",[]):
        if not isinstance(row,dict):
            raise ValueError("Invalid QB review row")
        game=games.get(str(row.get("game_id")))
        if game is None:
            continue  # game kicked off during collection: never freeze it from this queue
        team=row.get("team")
        if (team not in (game["home"],game["away"])
            or row.get("kickoff_utc")!=game["kickoff_utc"]
            or row.get("opponent")!=(game["away"] if team==game["home"] else game["home"])):
            raise ValueError("QB queue team/opponent/kickoff mismatch")
        slot=(str(game["game_id"]),team)
        if slot in seen:
            raise ValueError("Duplicate QB review game/team")
        seen.add(slot)
        qb=(game.get("verified_qb_starters") or {}).get(team)
        confirmed=isinstance(qb,dict) and bool(qb.get("player") and qb.get("source_url"))
        expected="VERIFIED_SOURCE" if confirmed else "UNKNOWN"
        if row.get("starter_status")!=expected:
            raise ValueError("QB queue starter is not supported by original context")
        if row.get("starter_player")!=(qb.get("player") if confirmed else None):
            raise ValueError("QB queue starter identity mismatch")
        if row.get("feed_status") not in FEED_STATES:
            raise ValueError("Unexpected QB source status")
        for item in row.get("news_candidates",[]):
            if not isinstance(item,dict) or item.get("status")!="UNREVIEWED_NEWS_CANDIDATE":
                raise ValueError("QB news candidate promoted without review")
            published=item.get("published_at_utc")
            if published and parse_time(published)>capture:
                raise ValueError("Future-dated news candidate")
        accepted.append(row)
    expected_slots={(str(g["game_id"]),team) for g in games.values()
                    for team in (g["home"],g["away"])}
    if seen!=expected_slots:
        raise ValueError("Incomplete QB team-game review coverage")
    return {"asof_utc":cutoff.isoformat(),"queue_captured_at_utc":capture.isoformat(),
            "status":"QB_REVIEW_RESEARCH_ONLY","rows":accepted,"summary":summarize(accepted),
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
