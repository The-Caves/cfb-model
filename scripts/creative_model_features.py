"""Research-only opponent/matchup and possession features from PRIOR 2026 games.

The provider's field position is play-weighted (not drive starts); score/drive
contains all scoreboard points, including potential special-teams/defense scores.
Turnover attribution and player injuries are NOT inferred from play-by-play.
Historical play-by-play publication time is not authenticated.
"""
import datetime as dt
import math
from collections import defaultdict

from scripts.experimental_matchup_features import augment
from scripts.model_v03 import game_stats, group_by_date, numeric, rate

STATUS = "CREATIVE_PRIOR_GAME_FEATURES_RESEARCH_ONLY"
HALF_LIFE = 14.
GROUPS = {
    "possession_context": ("possessions_proxy", "home_attack_ppd", "away_attack_ppd",
                            "home_defense_ppd", "away_defense_ppd", "drive_plays_diff"),
    "deserved_quality": ("epa_score_gap_diff", "play_weighted_field_position_diff"),
    "matchup_vulnerability": ("home_pressure_stress", "away_pressure_stress",
                               "pressure_pass_exposure_diff"),
    "drive_resilience": ("third_down_success_diff", "fourth_down_success_diff",
                          "explosive_dependence_diff", "pressure_resilience_diff"),
    "evolving_strength": ("recency_margin_shift_diff", "recency_epa_shift_diff",
                           "recency_coverage_diff")
}
CREATIVE_FIELDS = tuple(dict.fromkeys(f for names in GROUPS.values() for f in names))


def _delta(a, b):
    return None if a is None or b is None else float(a)-float(b)


def _average(a, b):
    return None if a is None or b is None else (float(a)+float(b))/2.


def _mean(values):
    return sum(values)/len(values) if values else None


def _weighted(history, name, day, half_life=HALF_LIFE, minimum=2):
    cutoff = dt.date.fromisoformat(day) if isinstance(day, str) else day
    terms = []
    for record in history:
        past = dt.date.fromisoformat(record["date"])
        if past >= cutoff:
            raise ValueError("Same-day or future advanced outcome leaked into history")
        value = record.get(name)
        if value is None:
            continue
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Nonfinite historical signal")
        weight = math.exp2(-(cutoff-past).days/half_life)
        terms.append((float(value), weight))
    if len(terms) < minimum:
        return None
    return sum(v*w for v,w in terms)/sum(w for _,w in terms)


def _season_mean(history, name, minimum=3):
    values = [r[name] for r in history if r.get(name) is not None]
    return _mean(values) if len(values)>=minimum else None


def _record(game, team, advanced):
    basic = game_stats(game, team, advanced)
    gid = game["game_id"]
    other = game["away"] if team==game["home"] else game["home"]
    p = advanced.get(gid, {}).get(team, {})
    q = advanced.get(gid, {}).get(other, {})
    drives = numeric(p, "drives")
    opponent_drives = numeric(q, "drives")
    plays = numeric(p, "scrimmage_plays")
    if drives is not None and not 1<=drives<=45:
        drives = None
    if opponent_drives is not None and not 1<=opponent_drives<=45:
        opponent_drives = None
    points = basic["points_for"]
    allowed = basic["points_against"]
    score_per_play = points/plays if plays is not None and plays>0 else None
    epa = basic.get("epa_off")
    gap = score_per_play - epa if score_per_play is not None and epa is not None else None
    total_explosives = numeric(p, "explosive_pass")
    rush_explosives = numeric(p, "explosive_rush")
    explosive = ((total_explosives+rush_explosives)/plays
                 if all(x is not None for x in (total_explosives, rush_explosives, plays))
                 and plays>0 else None)
    return {
        "date": game["date"], "game_id": str(gid),
        "margin": basic["margin"], "epa_off": epa,
        "epa_coverage": int(epa is not None),
        "drives": drives,
        "attack_ppd": points/drives if drives is not None else None,
        "defense_ppd": allowed/opponent_drives if opponent_drives is not None else None,
        "drive_plays": rate(p, "drive_plays_sum", "drives"),
        "score_epa_gap": gap,
        "play_weighted_field_position": rate(p, "field_position_sum", "field_position_n"),
        "pass_rate": basic.get("pass_rate"),
        "pressure_allowed": rate(p, "pressure_count", "pressure_observed"),
        "sack_generated": rate(q, "sack_count", "sack_observed"),
        "third_down_success": rate(p, "third_success", "third_plays"),
        "fourth_down_success": rate(p, "fourth_success", "fourth_plays"),
        "explosive_dependence": explosive
    }


def _features(home, away, day):
    def h(field, minimum=2): return _weighted(home, field, day, minimum=minimum)
    def a(field, minimum=2): return _weighted(away, field, day, minimum=minimum)
    possessions = _average(h("drives"), a("drives"))
    h_pressure = _average(h("pressure_allowed"), a("sack_generated"))
    a_pressure = _average(a("pressure_allowed"), h("sack_generated"))
    h_pass, a_pass = h("pass_rate"), a("pass_rate")
    h_explo, a_explo = h("explosive_dependence"), a("explosive_dependence")
    h_third, a_third = h("third_down_success"), a("third_down_success")
    h_fourth, a_fourth = h("fourth_down_success"), a("fourth_down_success")
    h_margin = _delta(h("margin"), _season_mean(home, "margin"))
    a_margin = _delta(a("margin"), _season_mean(away, "margin"))
    h_epa = _delta(h("epa_off"), _season_mean(home, "epa_off"))
    a_epa = _delta(a("epa_off"), _season_mean(away, "epa_off"))
    h_cover = _delta(h("epa_coverage"), _season_mean(home, "epa_coverage"))
    a_cover = _delta(a("epa_coverage"), _season_mean(away, "epa_coverage"))
    f = {
        "possessions_proxy": possessions,
        "home_attack_ppd": h("attack_ppd"),
        "away_attack_ppd": a("attack_ppd"),
        "home_defense_ppd": h("defense_ppd"),
        "away_defense_ppd": a("defense_ppd"),
        "drive_plays_diff": _delta(h("drive_plays"), a("drive_plays")),
        "epa_score_gap_diff": _delta(h("score_epa_gap"), a("score_epa_gap")),
        "play_weighted_field_position_diff":
            _delta(h("play_weighted_field_position"), a("play_weighted_field_position")),
        "home_pressure_stress": h_pressure,
        "away_pressure_stress": a_pressure,
        "pressure_pass_exposure_diff":
            _delta(h_pass*h_pressure if h_pass is not None and h_pressure is not None else None,
                   a_pass*a_pressure if a_pass is not None and a_pressure is not None else None),
        "third_down_success_diff": _delta(h_third, a_third),
        "fourth_down_success_diff": _delta(h_fourth, a_fourth),
        "explosive_dependence_diff": _delta(h_explo, a_explo),
        "pressure_resilience_diff":
            _delta(h_third-h_pressure if h_third is not None and h_pressure is not None else None,
                   a_third-a_pressure if a_third is not None and a_pressure is not None else None),
        "recency_margin_shift_diff": _delta(h_margin, a_margin),
        "recency_epa_shift_diff": _delta(h_epa, a_epa),
        "recency_coverage_diff": _delta(h_cover, a_cover)
    }
    if set(f)!=set(CREATIVE_FIELDS):raise ValueError("Feature schema mismatch")
    # Includes defense/special-team points. This is NOT observed offensive drive EPA.
    if all(f[k] is not None for k in ("possessions_proxy", "home_attack_ppd",
                                      "away_attack_ppd", "home_defense_ppd", "away_defense_ppd")):
        n = min(22., max(6., f["possessions_proxy"]))
        ph = min(70., max(0., n*(f["home_attack_ppd"]+f["away_defense_ppd"])/2))
        pa = min(70., max(0., n*(f["away_attack_ppd"]+f["home_defense_ppd"])/2))
        drive_prediction = (ph-pa, ph+pa)
    else:
        drive_prediction = None
    f["volatility_proxy"] = (_average(h_explo, a_explo) + 0.01*possessions
                             if _average(h_explo,a_explo) is not None and possessions is not None else None)
    f["possession_score_estimate"] = drive_prediction
    return f


def build(games, advanced):
    """One feature row per completed game, built before advancing its football date."""
    base = {str(row["game_id"]):row for row in augment(games, advanced)}
    if len(base)!=len(games):raise ValueError("Duplicate baseline game IDs")
    history=defaultdict(list)
    seen=set()
    for _, group in group_by_date(games):
        for game in group:
            gid=str(game["game_id"])
            if gid in seen:raise ValueError("Duplicate game")
            seen.add(gid)
            home,away=game["home"],game["away"]
            additions=_features(history[home],history[away],game["date"])
            base[gid].update(additions)
            base[gid]["creative_feature_source"]="PRIOR_2026_GAMES_RETROSPECTIVE_RECONSTRUCTION"
        for game in group:
            for team in (game["home"],game["away"]):
                history[team].append(_record(game,team,advanced))
    return [base[str(g["game_id"])] for g in games]


def verified_injury_pressure_interaction(home, away, home_pressure, away_pressure):
    """Research-only injury × pressure interaction; unknown reports stay missing.

    Only verified, timestamp-safe counts from observed_absences() are permitted.
    This function does NOT estimate point penalties or modify any live forecast.
    """
    def risk(side, stress):
        if side.get("coverage")!="VERIFIED_REPORT_REVIEWED" or side.get("absences") is None:
            return None
        if stress is None or not math.isfinite(stress) or stress<0:
            return None
        return int(side["absences"]["OL"])*float(stress)
    h,a=risk(home,home_pressure),risk(away,away_pressure)
    return {"home_ol_stressor":h,"away_ol_stressor":a,
            "stressor_difference":_delta(h,a),
            "model_points_adjusted":False,
            "unverified_absence_treated_healthy":False}
