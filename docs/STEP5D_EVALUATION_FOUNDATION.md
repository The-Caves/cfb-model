# Step 5D foundation — postgame settlements, chronological splits, and research metrics

**As of 2026-10-21:** Offline code and synthetic fixtures only; no authenticated FanDuel market feed, calibrated college-football model, or empirical wagering backtest exists. `PASS_UNVALIDATED` remains mandatory.

## What was added

1. `scripts/market_settlement.py` grades a **previously assembled pregame FanDuel market board** against completed ESPN scores. Moneylines, selection-side point spreads, and over/under totals are settled as WIN, LOSS, or PUSH. It matches exact ESPN game IDs, canonical home/away names and kickoff, rejects ambiguous or mismatched finals, and requires a recorded post-kickoff final retrieval timestamp. Pregame feature records and postgame outcome labels are emitted as **separate collections** connected only by `row_id`. It does not predict games.
2. `scripts/market_walkforward.py` builds strictly chronological fold manifests using timestamped pregame features and separately published final labels. Each fold trains only on games whose labels were **actually known before** its training cutoff, tests on new kickoff windows, and leaves incomplete future results explicitly pending. It refuses mixed game IDs, repeated game/market selections, late pregame inputs and hindsight outcome fields inside features. It returns row IDs and QA summaries, not quote histories or actual model results.
3. `scripts/market_evaluation.py` accepts separately produced, timestamped and versioned model probability outputs for held-out selections and computes **diagnostic** Brier score and log loss against a two-sided bookmaker no-vig probability baseline. It excludes PUSHes from these binary scores, rejects forecasts issued after their declared decision time, rejects training cutoffs after the forecast was produced or beyond the fold's training cutoff, and quarantines unmatched opposing-side quotes from the market baseline.

## Important boundaries

- The code **does not train any new college-football model**. Forecast probability inputs to the tests are fabricated to exercise the calculations. The current `scripts/predict.py` remains a score-only ridge baseline, not a calibrated ATS/O-U model.
- Brier and log loss over the **two sides of the same match** are correlated observations, not independent evidence. A better metric in a small sample does not mean statistically significant predictive skill or positive betting expected value. The output explicitly marks `statistical_significance_established=false` and `model_validated=false`.
- A two-sided normalized bookmaker price approximates a conditional market baseline. It does not directly model push probabilities or bookmaker execution terms, and it does not establish opening/closing price truth.
- These mechanics require authenticated, time-accurate *private* FanDuel source history and a genuine out-of-sample prediction log before performance may be reported. **No external paid odds API calls were made or scheduled.**
- The simulated code and unit tests may be public. Actual licensed odds, selection prices, wagering-account data, credentials, or derived private quote-board artifacts must **never** be put in public `main`, `context-state`, or public Actions artifacts.

## Validation checkpoint

[GitHub Actions validation run 39687070388](https://github.com/The-Caves/cfb-model/actions/runs/39687070388) completed **239 tests successfully**, including strict score grading, label/pregame separation, delayed-final leakage, selection-side pushes, chronological splits, held-out score metrics, market baseline eligibility, and impossible training-after-forecast chronology. The skipped `ingest` job is normal for a code-only push.

The model's work remaining before actual SU/ATS/O-U recommendations:

- Establish a properly licensed, secure and durable real FanDuel data feed with historical prices that can be joined as-of to actual ESPN pregame snapshots.
- Implement opponent-adjusted 2026 EPA/profile/QB/context features with true availability timestamps and separate prior-year training priors.
- Fit and freeze versioned forecast models, validate prediction timestamps, and compare against the sportsbook baseline in genuine chronological out-of-sample tests; account for game-level dependence and push rates.
- Add calibration, ablation testing, probability thresholds, CLV and genuine parlay joint-probability evaluation with price validation. Continue to return `PASS_UNVALIDATED` until there is credible evidence.

See [Step 5C market board](STEP5C_MARKET_FEATURE_BOARD.md) and [Step 5B source acceptance test](STEP5B_REAL_DATA_SMOKE.md) for earlier gates.
