"""Research-only grading of *previously frozen* bookmaker quotes.

The pregame board contains features; postgame scoreboard scores are LABELS
only. This module does not create predictions, calibrate a model, compute EV,
or authorize a bet. Do not publish private bookmaker prices to GitHub.
"""
from collections import Counter
from scripts.game_context import parse_time

SIDES={"MONEYLINE":("HOME","AWAY"),"SPREAD":("HOME","AWAY"),
       "TOTAL":("OVER","UNDER")}

def exact_score(value):
    if isinstance(value,bool):raise ValueError("Boolean is not a score")
    text=str(value).strip()
    if not text.isdecimal():raise ValueError("Score must be a nonnegative integer")
    score=int(text)
    if score>160:raise ValueError("Unreasonable final score")
    return score

def grade_selection(market,selection,line,home_score,away_score):
    """WIN / LOSS / PUSH from game results. No odds or model probability."""
    if market not in SIDES or selection not in SIDES[market]:
        raise ValueError("Unknown settlement side")
    margin=home_score-away_score
    if market=="MONEYLINE":
        if line is not None:raise ValueError("Moneyline must not have points")
        value=margin if selection=="HOME" else -margin
    elif market=="SPREAD":
        if type(line) not in (int,float):raise ValueError("Invalid spread")
        value=margin+line if selection=="HOME" else -margin+line
    else:
        if type(line) not in (int,float):raise ValueError("Invalid total")
        value=home_score+away_score-line
        if selection=="UNDER":value=-value
    return "WIN" if value>0.000001 else "LOSS" if value< -0.000001 else "PUSH"

def settle_markets(board,pregame_context,completed_games,finals_retrieved_at_utc):
    """Produce strictly labeled examples, without adding scores to features.

    Verified ESPN game identifiers, home/away assignment, and kickoff must
    agree. A final can be graded only once observed after kickoff. The final
    is never exposed inside the returned pregame feature records.
    """
    if board.get("status")!="PRIVATE_MARKET_RESEARCH_ONLY" or (
        board.get("betting_status")!="PASS_UNVALIDATED" or
        board.get("safe_for_betting") is not False):
        raise ValueError("Market board has invalid research status")
    decision=parse_time(board["decision_asof_utc"])
    context_asof=parse_time(pregame_context["asof_utc"])
    observed_final=parse_time(finals_retrieved_at_utc)
    if context_asof>decision:raise ValueError("Future pregame context")
    if observed_final<=decision:raise ValueError("Finals publication precedes decision cutoff")
    schedule={}
    for game in pregame_context["games"]:
        gid=str(game["game_id"])
        if gid in schedule:raise ValueError("Duplicate scheduled ESPN ID")
        schedule[gid]=game
    finals={}
    for game in completed_games:
        gid=str(game["game_id"])
        if gid in finals:raise ValueError("Duplicate final ESPN ID")
        finals[gid]=game
    seen=set();counts=Counter();feature_rows=[];label_rows=[]
    for event in board["events"]:
        gid=str(event["espn_game_id"])
        if gid in seen:raise ValueError("Duplicate market board ESPN ID")
        seen.add(gid)
        pre=schedule.get(gid)
        end=finals.get(gid)
        if pre is None:
            counts["missing_pregame_schedule"]+=1;continue
        kickoff=parse_time(pre["kickoff_utc"])
        if decision>=kickoff:
            counts["decision_not_before_kickoff"]+=1;continue
        if end is None:
            counts["final_not_available"]+=1;continue
        if observed_final<=kickoff:
            counts["final_retrieval_before_kickoff"]+=1;continue
        if str(end.get("home"))!=str(pre["home"]) or str(end.get("away"))!=str(pre["away"]):
            counts["final_team_mismatch"]+=1;continue
        if abs((parse_time(end["kickoff_utc"])-kickoff).total_seconds())>15*60:
            counts["final_kickoff_mismatch"]+=1;continue
        try:
            home=exact_score(end["home_score"])
            away=exact_score(end["away_score"])
        except (TypeError,ValueError):
            counts["invalid_final_score"]+=1;continue
        if (str(pre.get("home_id"))!=str(event["home_espn_team_id"]) or
            str(pre.get("away_id"))!=str(event["away_espn_team_id"])):
            counts["prematch_team_id_mismatch"]+=1;continue
        for market,info in event["markets"].items():
            if market not in SIDES:raise ValueError("Unknown market type")
            if info.get("status")!="RECENT_OBSERVED_NOT_EXECUTABLE":
                counts["stale_or_untimed_market"]+=1;continue
            if set(info.get("selections",{}))!=set(SIDES[market]):
                counts["incomplete_market"]+=1;continue
            if (parse_time(info["latest_observed_at_utc"])>decision or
                parse_time(info["latest_retrieved_at_utc"])>decision or
                parse_time(info["latest_observed_at_utc"])>=kickoff):
                raise ValueError("Post-cutoff odds entered research board")
            for side in SIDES[market]:
                quote=info["selections"][side]
                result=grade_selection(market,side,quote["line_points"],home,away)
                row_id="|".join((gid,board["bookmaker"],market,side,
                                 board["decision_asof_utc"]))
                # Features intentionally omit all final scores or outcome data.
                feature_rows.append({
                    "row_id":row_id,"espn_game_id":gid,
                    "decision_asof_utc":board["decision_asof_utc"],
                    "pregame_context_asof_utc":pregame_context["asof_utc"],
                    "kickoff_utc":pre["kickoff_utc"],"bookmaker":board["bookmaker"],
                    "market":market,"selection":side,
                    "line_points":quote["line_points"],
                    "american_odds":quote["american_odds"],
                    "market_observed_at_utc":info["latest_observed_at_utc"],
                    "market_retrieved_at_utc":info["latest_retrieved_at_utc"],
                    "market_source_sha256":info["latest_observed_source_sha256"],
                    "status":"PREGAME_RESEARCH_FEATURE_ONLY"})
                label_rows.append({"row_id":row_id,"espn_game_id":gid,
                    "outcome_known_at_utc":finals_retrieved_at_utc,
                    "settlement":result,"status":"POSTGAME_LABEL_ONLY"})
                counts["graded_sides"]+=1
        counts["matched_completed_games"]+=1
    return {"features":feature_rows,"postgame_labels":label_rows,
            "qa":dict(counts),"status":"PRE_AND_POSTGAME_SEPARATED_RESEARCH",
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
