"""V07: source-observed within-team QB scoring cohort shadow, never a pick.

Compare the named expected quarterback's recorded pass-touchdown *production*
against other dominant passers on the SAME team in earlier 2026 games. This
is deliberately a high-variance, NONCAUSAL replacement hypothesis. Only
teams with a genuine change from their most recent named dominant passer,
multiple historical games on both sides, and source-matched V04 baseline may
receive a bounded candidate point adjustment. Others PASS. No historical
leading passer is promoted to a current starter.

The 6 points / passing TD conversion is a football scoring upper-bound proxy
for this *research ablation*, NOT a fitted causal QB value. Opponent mix,
receiving skill, defensive turnovers and coaching are still confounded.
Never change a frozen V04 score or claim an independently validated lift.
"""
import math
from collections import defaultdict
from zoneinfo import ZoneInfo

from scripts.game_context import parse_time
from scripts.site_depthchart import qb_name_key
from scripts.v04_direct_scores import MODEL as V04_MODEL, STATUS as V04_STATUS

MODEL="V07_EXPECTED_QB_WITHIN_TEAM_PASS_TD_COHORT_SHADOW"
STATUS="CFB_V07_OBSERVED_QB_SCORE_RESEARCH_ONLY"
ET=ZoneInfo("America/New_York")
MIN_DOMINANT_PASS_ATTEMPTS=10
MIN_PASS_ATTEMPT_SHARE=.80
MIN_PLAYER_GAMES=2
MIN_OTHER_GAMES=2
RECENT_GAMES=8
PSEUDO_GAMES=4.
SCORING_PROXY_POINTS_PER_PASS_TD=6.
MAX_PER_TEAM_POINTS=3.5


def _valid_score(v04):
    if not isinstance(v04,dict) or v04.get("model")!=V04_MODEL or (
        v04.get("status")!=V04_STATUS or
        v04.get("model_promoted") is not False or
        v04.get("no_market_lines_in_training") is not True or
        v04.get("direct_scoring_fit_uses_v03_total") is not False):
        return False
    return all(type(v04.get(k)) in (int,float) and math.isfinite(v04[k])
               for k in ("home_points","away_points","home_margin","total_points")) and (
        v04["home_points"]>=0 and v04["away_points"]>=0 and
        abs(v04["home_points"]+v04["away_points"]-v04["total_points"])<.04 and
        abs(v04["home_points"]-v04["away_points"]-v04["home_margin"])<.04)


def _ref(rows,past_schedule,now):
    """Use only 2026 source-matched ESPN player rows from earlier football days."""
    today=now.astimezone(ET).date()
    bucket=defaultdict(list)
    for row in rows:
        gameid=str(row["game_id"])
        g=past_schedule.get(gameid)
        if not g:
            continue  # source parser already quarantined unmatched fixtures
        kick=parse_time(g["kickoff_utc"])
        observed=parse_time(row["observed_at_utc"])
        if observed>now or kick>=now:
            raise ValueError("Future player box record in QB scoring reference")
        if kick.astimezone(ET).date()>=today:
            continue  # a same-day finished game cannot inform today's kickoff
        teamid=str(row["team_id"])
        if teamid not in (str(g["home_id"]),str(g["away_id"])):
            raise ValueError("QB stat associated with another school's game")
        vals=row["values"]
        attempts=vals.get("passing_attempts")
        tds=vals.get("passing_touchdowns")
        if type(attempts) is not int or type(tds) is not int:
            continue
        if not 0<=attempts<=150 or not 0<=tds<=30 or tds>attempts:
            raise ValueError("Impossible QB attempts or touchdowns")
        if attempts==0:continue
        player=qb_name_key(row["player_name"])
        pid=str(row["player_id"])
        if not player or not pid:
            raise ValueError("Unidentified historical quarterback")
        bucket[(teamid,gameid)].append({
            "player":player,"player_id":pid,"name":row["player_name"],
            "attempts":attempts,"touchdowns":tds,
            "kickoff_utc":g["kickoff_utc"]})
    by_team=defaultdict(list)
    for (team,gameid),players in bucket.items():
        total=sum(x["attempts"] for x in players)
        if total<MIN_DOMINANT_PASS_ATTEMPTS:continue
        ranked=sorted(players,key=lambda x:-x["attempts"])
        leader=ranked[0]
        if leader["attempts"]/total<MIN_PASS_ATTEMPT_SHARE:
            continue  # no uniquely dominant passer; never guess a starter
        # No two different IDs may share the dominant normalized name in
        # a game. This deliberately abstains on ambiguous identity records.
        if sum(x["player"]==leader["player"] for x in players)!=1:
            continue
        by_team[team].append({
            "game_id":gameid,"player":leader["player"],
            "player_id":leader["player_id"],"name":leader["name"],
            "passing_touchdowns":leader["touchdowns"],
            "pass_attempt_share":round(leader["attempts"]/total,5),
            "kickoff_utc":leader["kickoff_utc"]})
    for team in by_team:
        by_team[team].sort(key=lambda x:(parse_time(x["kickoff_utc"]),x["game_id"]))
    return by_team


def _side(selection,history):
    name=selection.get("player") if isinstance(selection,dict) else None
    status=selection.get("status") if isinstance(selection,dict) else None
    result={"expected_qb":name,"identity_evidence":status or "UNKNOWN",
            "status":"PASS_NO_CURRENT_EXPECTED_QB",
            "observed_games_considered":len(history),
            "selected_qb_games":0,"other_qb_games":0,
            "latest_dominant_passer":history[-1]["name"] if history else None,
            "adjustment_points":0.,
            "peer_comparison_is_not_verified_starter_label":True}
    if not name or status not in ("PROJECTED_DEPTH_CHART","CONFIRMED_THIS_GAME"):
        return result
    if len(history)<MIN_PLAYER_GAMES+MIN_OTHER_GAMES:
        result["status"]="PASS_NO_COMPARABLE_SAME_TEAM_QB_COHORT"
        return result
    target=qb_name_key(name)
    # Multiple athletes with identical team/name: do not merge histories.
    ids={x["player_id"] for x in history if x["player"]==target}
    if len(ids)>1:
        result["status"]="PASS_AMBIGUOUS_ATHLETE_ID"
        return result
    recent=history[-RECENT_GAMES:]
    selected=[x for x in recent if x["player"]==target]
    peers=[x for x in recent if x["player"]!=target]
    result["selected_qb_games"]=len(selected)
    result["other_qb_games"]=len(peers)
    if len(selected)<MIN_PLAYER_GAMES or len(peers)<MIN_OTHER_GAMES:
        result["status"]="PASS_INSUFFICIENT_BOTH_QB_COHORT_GAMES"
        return result
    if recent[-1]["player"]==target:
        result["status"]="PASS_NO_OBSERVED_CHANGE_FROM_LAST_DOMINANT_QB"
        return result
    selected_td=sum(x["passing_touchdowns"] for x in selected)/len(selected)
    peers_td=sum(x["passing_touchdowns"] for x in peers)/len(peers)
    team_td=sum(x["passing_touchdowns"] for x in recent)/len(recent)
    shrink=(len(selected)/(len(selected)+PSEUDO_GAMES)*
            len(peers)/(len(peers)+PSEUDO_GAMES))
    # A difference in observed TDs is not necessarily caused by the QB.
    # The strong shrinkage and cap prevent unsupported large point swings.
    raw=(selected_td-team_td)*SCORING_PROXY_POINTS_PER_PASS_TD*shrink
    delta=max(-MAX_PER_TEAM_POINTS,min(MAX_PER_TEAM_POINTS,raw))
    result.update({
        "status":"QUALIFIED_NONCAUSAL_QB_COHORT_SHADOW",
        "adjustment_points":round(delta,5),
        "current_qb_historical_pass_tds_per_game":round(selected_td,5),
        "other_qbs_historical_pass_tds_per_game":round(peers_td,5),
        "team_recent_pass_tds_per_game":round(team_td,5),
        "shrinkage":round(shrink,6),
        "latest_dominant_passer_is_not_verified_starter":True,
        "same_team_history_only":True,
        "historical_game_ids":[x["game_id"] for x in recent]})
    return result


def attach(board,rows,past_schedule,current_schedule,observed_at_utc,source_hashes=None):
    """Attach non-promoted V07 shadow to the same V04 games, never mutate picks."""
    now=parse_time(observed_at_utc)
    if board.get("schema_version")!=2 or board.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Untrusted football research board")
    history=_ref(rows,past_schedule,now)
    used=0
    qualified=0
    sides=0
    for g in board["games"]:
        gameid=str(g["game_id"])
        kick=parse_time(g["kickoff_utc"])
        if kick<=now:raise ValueError("V07 cannot forecast an already-started fixture")
        score=g.get("v04_direct_scores")
        matchup=current_schedule.get(gameid)
        valid=bool(matchup and
            str(matchup.get("game_id"))==gameid and
            str(matchup.get("home_id"))!=str(matchup.get("away_id")))
        per={}
        for side in ("home","away"):
            selection=g.get("qb_pregame_"+side)
            teamid=str(matchup[side+"_id"]) if valid else ""
            per[side]=_side(selection,history.get(teamid,[]))
        if not valid or not _valid_score(score):
            record={"status":"PASS_NO_MATCHED_V04_AND_ESPN_FIXTURE",
                    "predicted_home_points":None,"predicted_away_points":None,
                    "predicted_home_margin":None,"predicted_total_points":None}
        else:
            qualified_sides=sum(x["status"]=="QUALIFIED_NONCAUSAL_QB_COHORT_SHADOW"
                                for x in per.values())
            sides+=qualified_sides
            if not qualified_sides:
                record={"status":"PASS_NO_QUALIFIED_QB_COHORT",
                        "predicted_home_points":None,"predicted_away_points":None,
                        "predicted_home_margin":None,"predicted_total_points":None}
            else:
                base_home=float(score["home_points"])
                base_away=float(score["away_points"])
                hp=max(0.,base_home+per["home"]["adjustment_points"])
                ap=max(0.,base_away+per["away"]["adjustment_points"])
                total=hp+ap
                if total<=0:raise ValueError("Impossible V07 expected scoring total")
                clamped=max(20.,min(110.,total))
                hp=round(hp*clamped/total,4)
                ap=round(ap*clamped/total,4)
                record={"status":"NONCAUSAL_QB_COHORT_RESEARCH_SHADOW",
                        "predicted_home_points":hp,"predicted_away_points":ap,
                        "predicted_home_margin":round(hp-ap,4),
                        "predicted_total_points":round(hp+ap,4)}
                qualified+=1
        g["v07_personnel_shadow"]={
            **record,"model":MODEL,"observed_at_utc":now.isoformat(),
            "source_hashes":source_hashes or {},
            "base_v04_home_margin":score["home_margin"] if _valid_score(score) else None,
            "base_v04_total_points":score["total_points"] if _valid_score(score) else None,
            "qb_cohorts":per,
            "is_noncausal_pass_td_proxy":True,
            "passing_td_to_points_proxy":SCORING_PROXY_POINTS_PER_PASS_TD,
            "same_day_games_embargoed":True,
            "historical_source_first_publication_authenticated":False,
            "replacement_starter_participation_verified":False,
            "trained_on_actual_verified_replacement_labels":False,
            "not_a_betting_recommendation":True,
            "market_odds_used_for_training":False,
            "score_model_promoted":False,
            "changes_frozen_scores":False,
            "betting_status":"PASS_UNVALIDATED"}
        used+=1
    board["v07_personnel_research"]={
        "status":STATUS,"model":MODEL,
        "total_games":used,"qualified_shadow_games":qualified,
        "qualified_historical_peer_sides":sides,
        "max_qb_team_point_adjustment":MAX_PER_TEAM_POINTS,
        "trained_on_verified_starter_changes":False,
        "measured_prospective_heldout_lift":False,
        "market_odds_used":False,"score_model_promoted":False,
        "changes_original_score_forecasts":False,
        "betting_status":"PASS_UNVALIDATED",
        "description":"Conservative same-team, previously observed dominant-passer passing-TD contrast. No change to V04; do not infer causal QB value."}
    return board
