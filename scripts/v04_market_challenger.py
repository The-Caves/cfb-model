"""Source-gated, market-anchored V04 ATS / totals research challenger.

This is a prospective selection *policy* applied to independently frozen V04
scores and subsequently observed pre-kickoff sportsbook quotes. It does not
train V04 on odds, does not backfill player availability, and is not a betting
model or a proven improvement. Thresholds are fixed before any new grades.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path

from scripts.game_context import parse_time
from scripts.v04_direct_scores import MODEL as SCORE_MODEL, STATUS as SCORE_STATUS

STATUS = "V04_MARKET_ANCHORED_RESEARCH_PASS_GATED"
POLICY = "V04_FIXED_RESIDUAL_RULE_20261101_V1"
MIN_ATS_VERIFIED = 6.0
MIN_ATS_UNKNOWN_QB = 8.0
MAX_ATS = 18.0
MIN_OU_VERIFIED = 8.0
MIN_OU_UNKNOWN_QB = 10.0
MAX_OU = 24.0
ATS_SHRINK = 0.30
OU_SHRINK = 0.25


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def decide(score, spread, total, provider, quote_utc, kickoff_utc,
           captured_utc, qb_verified=0):
    """Choose a research side only when evidence clears conservative gates.

    The quote and prediction are independent timestamps; a quote observed
    after the original score forecast is never recast as having been there
    at model-training time. No game with an unsupported source gets a side.
    """
    if (not isinstance(score, dict) or
        score.get("model") != SCORE_MODEL or score.get("status") != SCORE_STATUS or
        score.get("direct_scoring_fit_uses_v03_total") is not False or
        score.get("no_market_lines_in_training") is not True or
        score.get("model_promoted") is not False):
        raise ValueError("V04 score provenance required")
    margin = score.get("home_margin")
    projected = score.get("total_points")
    home = score.get("home_points")
    away = score.get("away_points")
    if (not all(finite(v) for v in (margin, projected, home, away)) or
        min(home, away, projected) < 0 or
        abs(home + away - projected) > .03 or
        abs(home - away - margin) > .03):
        raise ValueError("V04 score values incoherent")
    if type(qb_verified) is not int or qb_verified not in (0, 1, 2):
        raise ValueError("Invalid verified QB coverage")
    kickoff = parse_time(kickoff_utc)
    captured = parse_time(captured_utc)
    if captured >= kickoff:
        raise ValueError("Research decision cannot occur after kickoff")
    sp = spread is not None
    tt = total is not None
    if sp and (not finite(spread) or abs(spread) >= 80):
        raise ValueError("Invalid pregame spread")
    if tt and (not finite(total) or not 0 < total < 150):
        raise ValueError("Invalid pregame total")
    if sp or tt:
        if not isinstance(provider, str) or not provider.strip() or not quote_utc:
            raise ValueError("Observed market source is required")
        quote = parse_time(quote_utc)
        if quote > captured or quote >= kickoff:
            raise ValueError("Market quote is late")
    elif provider is not None or quote_utc is not None:
        raise ValueError("Market provider timestamp without quote")
    qb_unknown = qb_verified != 2
    min_ats = MIN_ATS_UNKNOWN_QB if qb_unknown else MIN_ATS_VERIFIED
    min_ou = MIN_OU_UNKNOWN_QB if qb_unknown else MIN_OU_VERIFIED
    ats_gap = round(margin + spread, 4) if sp else None
    total_gap = round(projected - total, 4) if tt else None

    def side(value, minimum, maximum, positive, negative):
        if value is None:
            return "PASS", "NO_SOURCE_VERIFIED_LINE"
        if abs(value) < minimum:
            return "PASS", "INSUFFICIENT_MODEL_MARKET_DISAGREEMENT"
        if abs(value) > maximum:
            return "PASS", "UNRELIABLE_EXTREME_MODEL_MARKET_CONFLICT"
        return (positive if value > 0 else negative), "PREDEFINED_RESEARCH_THRESHOLD"

    ats, ats_reason = side(ats_gap, min_ats, MAX_ATS, "HOME", "AWAY")
    ou, ou_reason = side(total_gap, min_ou, MAX_OU, "OVER", "UNDER")
    return {
        "status": STATUS, "policy": POLICY,
        "ats_side": ats, "ou_side": ou,
        "ats_reason": ats_reason, "ou_reason": ou_reason,
        "raw_ats_model_market_gap": ats_gap,
        "raw_ou_model_market_gap": total_gap,
        "market_implied_home_margin": round(-spread, 4) if sp else None,
        "market_anchored_home_margin": round(-spread + ATS_SHRINK * ats_gap, 4)
             if sp else None,
        "market_anchored_total": round(total + OU_SHRINK * total_gap, 4)
             if tt else None,
        "ats_min_gap": min_ats, "ou_min_gap": min_ou,
        "verified_qbs_at_display": qb_verified,
        "missing_verified_qb_warning": qb_unknown,
        "quote_observed_at": quote_utc if sp or tt else None,
        "predefined_not_fitted_on_results": True,
        "score_model_promoted": False,
        "research_policy_promoted": False,
        "market_lines_not_model_training_inputs": True,
        "market_publication_at_score_forecast_not_authenticated": True,
        "validated_betting_edge": False,
        "betting_status": "PASS_UNVALIDATED",
    }


def apply(board, now):
    if (board.get("schema_version") != 2 or
        board.get("betting_status") != "PASS_UNVALIDATED"):
        raise ValueError("Unexpected dashboard")
    now = parse_time(now) if isinstance(now, str) else now
    summary = {"eligible_v04_games": 0, "ats_research_sides": 0,
               "ou_research_sides": 0, "qb_uncertain_games": 0}
    for game in board["games"]:
        game["v04_market_research"] = None
        score = game.get("v04_direct_scores")
        if score is None:
            continue
        if game.get("home_bias_quarantined") is not True:
            raise ValueError("Independent V04 cannot rewrite active V03")
        if parse_time(game["kickoff_utc"]) <= now:
            continue
        result = decide(
            score, game.get("market_home_spread"), game.get("market_total"),
            game.get("market_provider"), game.get("market_observed_utc"),
            game["kickoff_utc"], now.isoformat(),
            game.get("qb_starters_verified", 0),
        )
        game["v04_market_research"] = result
        summary["eligible_v04_games"] += 1
        summary["ats_research_sides"] += result["ats_side"] != "PASS"
        summary["ou_research_sides"] += result["ou_side"] != "PASS"
        summary["qb_uncertain_games"] += result["missing_verified_qb_warning"]
    board["v04_market_research_audit"] = {
        "status": STATUS, "policy": POLICY, **summary,
        "fixed_policy_not_backtested_or_promoted": True,
        "no_validated_wager_recommendations": True,
        "market_is_observed_only_at_build": True,
        "score_training_untouched": True,
    }
    return board


def run(dashboard, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    path = Path(dashboard)
    board = json.loads(path.read_text(encoding="utf-8"))
    result = apply(board, now)
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")
    print(json.dumps(result["v04_market_research_audit"], sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True)
    args = parser.parse_args()
    run(args.dashboard)
