"""Reproducible possession/field-position/drive-outcome simulation.

Only consumes predecision empirical distributions supplied by another audited
fitting stage. It does NOT invent those distributions, assume calibration, or
silently create sportsbook lines. An exploratory conditional-drive simulator,
not yet a validated full-play or in-game game engine.
"""
import argparse
import json
import math
import random
from pathlib import Path

from scripts.game_context import parse_time

STATUS = "CONDITIONAL_DRIVE_SIMULATION_RESEARCH_ONLY"
SOURCE = "FROZEN_PREDECISION_DRIVE_DISTRIBUTIONS_RESEARCH_ONLY"
POINTS = {0, 2, 3, 6, 7, 8}


def _sample(rng, rows, field, allowed=None):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Empty empirical drive distribution")
    total = 0.0
    for item in rows:
        value = item.get(field)
        weight = item.get("weight")
        if (allowed is not None and value not in allowed) or (
                type(weight) not in (int, float) or not math.isfinite(weight) or weight <= 0):
            raise ValueError("Invalid empirical distribution entry")
        total += weight
    draw = rng.random() * total
    for item in rows:
        draw -= item["weight"]
        if draw < 0:
            return item
    return rows[-1]


def _finite(x, name):
    if type(x) not in (float, int) or not math.isfinite(x):
        raise ValueError("Invalid "+name)
    return float(x)


def validate_inputs(fitted, decision_utc, market=None):
    decision = parse_time(decision_utc)
    if fitted.get("status") != SOURCE or fitted.get("betting_status") != "PASS_UNVALIDATED":
        raise ValueError("Untrusted simulation fit")
    if fitted.get("safe_for_betting") is not False or fitted.get("model_promoted") is not False:
        raise ValueError("Research simulation cannot be automatically promoted")
    if not fitted.get("game_id") or not fitted.get("home") or not fitted.get("away"):
        raise ValueError("Missing game identity")
    if fitted["home"] == fitted["away"]:
        raise ValueError("Invalid matchup")
    if not (parse_time(fitted["trained_through_utc"]) <=
            parse_time(fitted["source_captured_at_utc"]) <= decision <
            parse_time(fitted["kickoff_utc"])):
        raise ValueError("Future-trained or postkickoff simulation inputs")
    dist = fitted["distributions"]
    for p in dist["possessions"]:
        if "count" in p:
            if type(p["count"]) is not int or not 1<=p["count"]<=24:
                raise ValueError("Invalid paired possession count")
        elif (type(p.get("home_count")) is not int or type(p.get("away_count")) is not int
              or not 1<=p["home_count"]<=24 or not 1<=p["away_count"]<=24):
            raise ValueError("Invalid team-specific possession count")
    _sample(random.Random(0), dist["possessions"], "weight")
    zones = {r["zone"] for r in dist["field_position"]}
    if not zones or any(type(z) is not str or not z for z in zones):
        raise ValueError("Invalid starting field-position zones")
    _sample(random.Random(0), dist["field_position"], "zone", zones)
    per_side=dist.get("field_position_by_side")
    if per_side is not None and set(per_side)!={"home","away"}:
        raise ValueError("Both team-specific field position distributions required")
    for team in ("home", "away"):
        if per_side is not None:
            _sample(random.Random(0), per_side[team], "zone", zones)
            if {r["zone"] for r in per_side[team]}!=zones:
                raise ValueError("Missing team-specific field-zone coverage")
        if set(dist["outcomes"][team]) != zones:
            raise ValueError("Missing team/field conditional outcomes")
        for zone in zones:
            choices = dist["outcomes"][team][zone]
            _sample(random.Random(0), choices, "points", POINTS)
            if any(type(x.get("explosive")) is not bool for x in choices):
                raise ValueError("Explosive outcome requires empirical flag")
    if market is not None:
        if market.get("status") != "OBSERVED_PREDECISION_MARKET" or not (
                isinstance(market.get("source_url"), str) and
                market["source_url"].startswith("https://")):
            raise ValueError("Market input lacks observed source")
        if parse_time(market["observed_at_utc"]) > decision:
            raise ValueError("Postdecision market leakage")
        _finite(market.get("home_spread"), "home spread")
        _finite(market.get("total"), "total line")


def simulate(fitted, decision_utc, market=None, trials=5000, seed=2026):
    validate_inputs(fitted, decision_utc, market)
    if type(trials) is not int or not 100 <= trials <= 100000:
        raise ValueError("Invalid trial count")
    if type(seed) is not int:
        raise ValueError("Seed must be an integer")
    rng = random.Random(seed)
    dist = fitted["distributions"]
    margins, totals, homes, aways, explosives = [], [], [], [], []
    home_wins = away_wins = ties = 0
    covers = unders = overs = pushes_spread = pushes_total = 0
    for _ in range(trials):
        possession = _sample(rng, dist["possessions"], "weight")
        counts = {s: possession.get(s+"_count", possession.get("count")) for s in ("home", "away")}
        scores = {"home": 0, "away": 0}
        explosive_drives = 0
        for side in ("home", "away"):
            for _drive in range(counts[side]):
                source=(dist.get("field_position_by_side") or {}).get(side,dist["field_position"])
                zone = _sample(rng, source, "zone")["zone"]
                outcome = _sample(rng, dist["outcomes"][side][zone], "points")
                scores[side] += outcome["points"]
                explosive_drives += int(outcome["explosive"])
        h, a = scores["home"], scores["away"]
        margin, total = h-a, h+a
        margins.append(margin); totals.append(total)
        homes.append(h); aways.append(a); explosives.append(explosive_drives)
        home_wins += margin > 0
        away_wins += margin < 0
        ties += margin == 0  # Regulation ties: no pretend overtime rules.
        if market is not None:
            ats = margin+market["home_spread"]
            covers += ats > 0
            pushes_spread += ats == 0
            ou = total-market["total"]
            overs += ou > 0
            unders += ou < 0
            pushes_total += ou == 0
    def avg(xs): return round(sum(xs)/len(xs), 5)
    def quant(xs, pct):
        xs = sorted(xs)
        return xs[int((len(xs)-1)*pct)]
    result = {
        "status": STATUS, "game_id": str(fitted["game_id"]),
        "home": fitted["home"], "away": fitted["away"],
        "kickoff_utc": fitted["kickoff_utc"], "forecast_issued_utc": parse_time(decision_utc).isoformat(),
        "seed": seed, "simulations": trials,
        "home_points_mean": avg(homes), "away_points_mean": avg(aways),
        "home_margin_mean": avg(margins), "total_mean": avg(totals),
        "margin_p05_p50_p95": [quant(margins,p) for p in (0.05,0.5,0.95)],
        "total_p05_p50_p95": [quant(totals,p) for p in (0.05,0.5,0.95)],
        "explosive_drives_mean": avg(explosives),
        "home_win_regulation_probability": round(home_wins/trials, 6),
        "away_win_regulation_probability": round(away_wins/trials, 6),
        "regulation_tie_probability": round(ties/trials, 6),
        "home_cover_probability": round(covers/trials,6) if market else None,
        "spread_push_probability": round(pushes_spread/trials,6) if market else None,
        "over_probability": round(overs/trials,6) if market else None,
        "under_probability": round(unders/trials,6) if market else None,
        "total_push_probability": round(pushes_total/trials,6) if market else None,
        "market_quote": market,
        "assumptions": [
            "independent conditional drive outcomes and sampled two-team possession counts",
            "field-position and explosive distributions must be fitted from earlier sourced drives",
            "regulation only; no overtime, special-teams or defensive-score mechanism unless represented in prior drive events",
            "no evidence that the supplied distributions are calibrated without held-out grades",
        ],
        "model_promoted": False, "safe_for_betting": False, "betting_status": "PASS_UNVALIDATED",
    }
    return result


def run(fit_path, output_path, decision_utc, market_path=None, trials=5000, seed=2026):
    fit = json.loads(Path(fit_path).read_text(encoding="utf-8"))
    market = json.loads(Path(market_path).read_text(encoding="utf-8")) if market_path else None
    result = simulate(fit, decision_utc, market, trials, seed)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--fit", required=True); p.add_argument("--output", required=True)
    p.add_argument("--decision-utc", required=True); p.add_argument("--market")
    p.add_argument("--trials", type=int, default=5000); p.add_argument("--seed", type=int, default=2026)
    a = p.parse_args()
    run(a.fit, a.output, a.decision_utc, a.market, a.trials, a.seed)
