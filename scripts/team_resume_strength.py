"""As-of 2026 schedule strength, victories and record quality.

These are explicit RESEARCH team-resume metrics, not ESPN's proprietary
Strength of Record ranking. No post-cutoff results enter a past matchup.
The 2026 historical source publication dates remain unauthenticated.
"""
import argparse
import csv
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.site_home_bias_guard import HOME_ALLOWANCE, ratings

STATUS = "CFB_2026_ASOF_OPPONENT_RESUME_RESEARCH_ONLY"
PROBABILITY_MARGIN_SCALE = 12.0
MIN_RATING_GAMES = 25


def _win_prob(power, opponent_power, site):
    x = max(-18., min(18., (power - opponent_power + site) /
                           PROBABILITY_MARGIN_SCALE))
    return 1. / (1. + math.exp(-x))


def record_probability_at_least(wins, probabilities):
    """Poisson-binomial tail for an average (0-rated) team on that schedule.

    Lower tail probability means a more unusual/stronger observed W-L record.
    It is deliberately distinct from an official proprietary SOR metric.
    """
    if type(wins) is not int or not isinstance(probabilities, list) or not 0 <= wins <= len(probabilities):
        raise ValueError("Invalid SOR game/record evidence")
    distribution = [1.]
    for p in probabilities:
        if type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError("Invalid average-team opponent win probability")
        next_distribution = [0.] * (len(distribution) + 1)
        for count, value in enumerate(distribution):
            next_distribution[count] += value * (1. - p)
            next_distribution[count+1] += value * p
        distribution = next_distribution
    return max(0., min(1., sum(distribution[wins:])))


def _schedule(raw, cutoff):
    asof = dt.date.fromisoformat(str(cutoff))
    if asof.year != 2026:
        raise ValueError("2026 season only")
    eligible = []
    seen = set()
    for row in raw:
        gid = str(row.get("game_id", ""))
        if not gid or gid in seen:
            raise ValueError("Duplicate/missing original ESPN game ID in resume ledger")
        seen.add(gid)
        date = dt.date.fromisoformat(row["date"])
        if date.year != 2026:
            raise ValueError("Wrong season in ESPN resume ledger")
        if date >= asof:
            continue
        home, away = row["home"], row["away"]
        if not home or not away or home == away:
            raise ValueError("Invalid source teams for schedule strength")
        h, a = int(row["home_score"]), int(row["away_score"])
        if not 0 <= h <= 160 or not 0 <= a <= 160 or h == a:
            raise ValueError("Invalid settled source result")
        neutral = str(row["neutral"]).lower()
        if neutral not in ("true", "false", "1", "0"):
            raise ValueError("Missing source-neutral venue evidence")
        eligible.append({
            "game_id":gid, "date":date.isoformat(),
            "home":home, "away":away,
            "home_score":h, "away_score":a,
            "neutral":neutral in ("true", "1"),
        })
    eligible.sort(key=lambda x: (x["date"], x["game_id"]))
    return eligible


def calculate(games, cutoff):
    """Return complete, source-dated SOS/SOV/SOR metrics, not today's records.

    Opponent ratings use the same conservative ridge/Massey framework as the
    existing V04 opponent-rating research, with a 2.5-point home allowance.
    Only games whose Eastern football date precedes cutoff are included.
    """
    past = _schedule(games, cutoff)
    if len(past) < MIN_RATING_GAMES:
        return {"status": STATUS, "cutoff_date_exclusive":str(cutoff),
                "source_games":len(past), "ready":False,
                "reason":"INSUFFICIENT_EARLIER_COMPLETED_FOOTBALL_GAMES",
                "teams":{}, "historical_publication_verified":False}
    observations = [(g["home"],g["away"],
                     g["home_score"]-g["away_score"],g["neutral"]) for g in past]
    league_rating = ratings(observations)
    team_history = defaultdict(list)
    for game in past:
        for side, opponent_side in (("home","away"),("away","home")):
            team, opponent = game[side], game[opponent_side]
            won = int(game[side+"_score"] > game[opponent_side+"_score"])
            site = 0. if game["neutral"] else (
                HOME_ALLOWANCE if side == "home" else -HOME_ALLOWANCE)
            team_history[team].append({
                "game_id":game["game_id"],"date":game["date"],
                "opponent":opponent,"won":won,"site_points":site,
            })
    records={t:{"wins":sum(e["won"] for e in history),
                "games":len(history)} for t,history in team_history.items()}
    teams={}
    for team,history in sorted(team_history.items()):
        opponents = [league_rating[event["opponent"]] for event in history]
        wins = [event for event in history if event["won"]]
        strengths = [league_rating[e["opponent"]] for e in wins]
        # Average 0-rated team vs EXACT opponents & historically known venues.
        average_win_chances=[_win_prob(0.,league_rating[e["opponent"]],
                                      e["site_points"]) for e in history]
        victories = sum(e["won"] for e in history)
        chance = record_probability_at_least(victories,average_win_chances)
        wins_expected = sum(average_win_chances)
        last_four=history[-4:]
        teams[team]={
            "games_before_cutoff":len(history),
            "wins_before_cutoff":victories,
            "losses_before_cutoff":len(history)-victories,
            "asof_team_power_points":round(league_rating[team],5),
            "sos_opponent_power_points":round(sum(opponents)/len(opponents),5),
            "sos_avg_team_win_pct":round(wins_expected/len(history),6),
            "sov_defeated_opponent_power_points":round(
                sum(strengths)/len(strengths),5) if strengths else None,
            "sov_opponent_win_pct":round(
                sum(records[e["opponent"]]["wins"]/records[e["opponent"]]["games"]
                    for e in wins)/len(wins),6) if wins else None,
            "sor_probability_avg_team_at_least_record":round(chance,8),
            "sor_log10_rarity_score":round(-math.log10(max(chance,1e-12)),6),
            "record_wins_above_avg_team_expected":round(victories-wins_expected,5),
            "recent_four_wins":sum(e["won"] for e in last_four),
            "recent_four_sos_opponent_power_points":round(
                sum(league_rating[e["opponent"]] for e in last_four)/len(last_four),5),
            "historical_game_ids":[e["game_id"] for e in history],
            "resume_definition":"RESEARCH_AVERAGE_TEAM_RIDGE_OPPONENT_RATING",
            "minimum_games_for_model_use":3,
        }
    return {
        "status": STATUS,"season":2026,"cutoff_date_exclusive":str(cutoff),
        "source_games":len(past),"teams":teams,"ready":True,
        "average_team_reference_power_points":0.,
        "home_field_points":HOME_ALLOWANCE,
        "opponent_power_source":"PAST_2026_OPPONENT_ADJUSTED_SCORE_RATINGS",
        "sor_definition":"-log10(P[average team >= observed wins against past schedule])",
        "sos_definition":"mean as-of opponent power; lower expected 0-rated win pct is harder",
        "sov_definition":"mean as-of power of defeated opponents; null when no wins",
        "historical_publication_verified":False,
        "model_promoted":False,"betting_status":"PASS_UNVALIDATED",
    }


def run(games_csv, asof, out):
    with open(games_csv, encoding="utf-8-sig",newline="") as fh:
        games=list(csv.DictReader(fh))
    result=calculate(games,asof)
    target=Path(out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":STATUS,"cutoff":asof,
                       "source_games":result["source_games"],
                       "teams":len(result["teams"]),
                       "historical_publication_verified":False}))
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--games",required=True)
    parser.add_argument("--asof",required=True)
    parser.add_argument("--output",required=True)
    a=parser.parse_args()
    run(a.games,a.asof,a.output)
