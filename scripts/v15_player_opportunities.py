"""V15 player-opportunity error calibration on first-archived pregame forecasts.

Only explicitly first-frozen, participant-confirmed, game-and-athlete-matched
predictions may be paired with a later independently published player box.
Missing player box categories or inactive/unconfirmed players are NOT zeros.
Cannot fit using the aggregate 622-row PlayerForm grade (individual receipts
are not persisted in that aggregate), and must not make profitable prop claims.

The original V14 joint simulation is unmodified. V15 reports a separate
conditional *research expected-yard adjustment* only when sufficient authentic
individual historical grades exist. It does not rewrite conserved team budgets
or generate player prop odds.
"""
import math
from collections import defaultdict

from scripts.game_context import parse_time
from scripts.v14_player_scenarios import STATUS as ORIGINAL_STATUS

STATUS="V15_PRIOR_FROZEN_PLAYER_OPPORTUNITY_CALIBRATION_RESEARCH_ONLY"
STATS=("passing_yards","rushing_yards","receiving_yards")
PRIOR_EXPOSURES=70.
MIN_OBS=30
CAP={"passing_yards":15.,"rushing_yards":10.,"receiving_yards":10.}
REQUIRED_SOURCE="FIRST_FROZEN_PREGAME_PLAYER_PROJECTION"
REQUIRED_FINAL="INDEPENDENT_POSTGAME_ATHLETE_BOX"


def _number(x):
    return type(x) in (float,int) and math.isfinite(x)


def fit(records,asof_utc):
    """Reject any future or same-decision result rather than backfill it."""
    decision=parse_time(asof_utc)
    if not isinstance(records,list):
        raise ValueError("Individual immutable player-grade receipts required")
    seen=set();data=defaultdict(list);games=defaultdict(set)
    for row in records:
        key=(str(row.get("game_id","")),str(row.get("player_id","")),
             row.get("stat"))
        if (not all(key) or key in seen or key[2] not in STATS):
            raise ValueError("Duplicate/unsupported player-stat game receipt")
        seen.add(key)
        try:
            first=parse_time(row["first_forecast_observed_utc"])
            kickoff=parse_time(row["kickoff_utc"])
            final=parse_time(row["final_observed_utc"])
        except (KeyError,ValueError,TypeError) as e:
            raise ValueError("Missing authentic player source timestamps") from e
        if (not first<kickoff<final<decision or
            row.get("forecast_provenance")!=REQUIRED_SOURCE or
            row.get("final_provenance")!=REQUIRED_FINAL or
            row.get("pregame_player_status")!="CONFIRMED_ACTIVE" or
            row.get("outcome_stat_observed") is not True or
            type(row.get("forecast_sha256")) is not str or
            len(row["forecast_sha256"])!=64 or
            type(row.get("final_sha256")) is not str or
            len(row["final_sha256"])!=64 or
            not _number(row.get("forecast_yards")) or
            not _number(row.get("observed_yards")) or
            not 0<=row["forecast_yards"]<=900 or
            not -200<=row["observed_yards"]<=900):
            raise ValueError("Cannot use unconfirmed, after-cutoff or unsourced player result")
        stat=row["stat"]
        data[stat].append(row["observed_yards"]-row["forecast_yards"])
        games[stat].add(key[0])
    diagnostics={}
    for stat in STATS:
        xs=data[stat];n=len(xs)
        shift=max(-CAP[stat],min(CAP[stat],
            sum(xs)/(n+PRIOR_EXPOSURES)))
        diagnostics[stat]={
            "source_paired_observations":n,
            "source_paired_games":len(games[stat]),
            "ready":n>=MIN_OBS and len(games[stat])>=10,
            "yard_shift":round(shift,6) if n>=MIN_OBS and len(games[stat])>=10 else 0.,
            "historical_mean_signed_error":round(sum(xs)/n,5) if n else None,
        }
    return {"status":STATUS,"asof_utc":decision.isoformat(),
            "source_paired_observations":sum(len(x) for x in data.values()),
            "categories":diagnostics,
            "prior_exposures":PRIOR_EXPOSURES,
            "confirmed_active_only":True,
            "unknown_participants_not_imputed":True,
            "original_simulator_conservation_preserved":True,
            "original_v14_player_scenarios_modified":False,
            "individual_prop_market_lines_available":False,
            "independent_prospective_edge_proven":False,
            "model_promoted":False,"safe_for_betting":False}


def research_projection(v14_result,calibration,decision_utc):
    """Separate review-only adjusted means; don't touch V14 draws/budgets."""
    decision=parse_time(decision_utc)
    if (v14_result.get("status")!=ORIGINAL_STATUS or
        v14_result.get("team_opportunities_conserved") is not True or
        v14_result.get("unknown_athletes_preserved") is not True or
        v14_result.get("model_promoted") is not False or
        calibration.get("status")!=STATUS or
        calibration.get("model_promoted") is not False or
        parse_time(calibration["asof_utc"])>decision or
        parse_time(v14_result["decision_utc"])>decision or
        decision>=parse_time(v14_result["kickoff_utc"])):
        raise ValueError("V15 player calibration not originally observed before kickoff")
    records=[]
    for team in v14_result["player_opportunity_scenarios"]:
        for player in team["player_opportunity_scenarios"]:
            if player["is_unmodeled_bucket"]:
                continue # Preserve unknown-player opportunity explicitly.
            for stat in STATS:
                if stat not in player["metrics"]:continue
                settings=calibration["categories"][stat]
                base=player["metrics"][stat]["mean"]
                if not _number(base) or base<0:raise ValueError("Invalid source simulation mean")
                records.append({
                    "team":team["team"],"player_id":player["player_id"],"stat":stat,
                    "v14_conditional_mean":base,
                    "v15_diagnostic_mean":round(max(0.,base+settings["yard_shift"]),4)
                     if settings["ready"] else None,
                    "source_sample_size":settings["source_paired_observations"],
                    "ready":settings["ready"],
                    "not_jointly_conserved":True,
                    "no_verified_betting_edge":True})
    return {"status":STATUS,"game_id":v14_result["game_id"],
            "player_conditionally_active_projections":records,
            "original_team_player_opportunities":v14_result["player_opportunity_scenarios"],
            "original_team_stat_conservation_preserved":True,
            "adjusted_means_are_not_conserved_team_stat_budgets":True,
            "missing_player_category_yielded_no_projection":True,
            "no_sportsbook_prop_lines_generated":True,
            "model_promoted":False,"safe_for_betting":False}
