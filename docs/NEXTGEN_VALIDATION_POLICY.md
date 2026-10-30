# Next-gen research validation — 2026-10-30

The nextgen_walkforward module builds descriptive matchup features from the
source-matched 2026 PBP/ESPN game ledger. The code freezes each team's profile
from earlier **Eastern football dates**, including opponent-adjusted rush/pass,
red-zone and pressure matchup context, verified-boxscore turnover features,
nonlinear pressure/rush/explosive interactions and recency trajectories.

Each candidate is tested against a **separately refitted V03** on precisely
the same training observations and held-out game IDs in each chronological
seven-day fold. Models that cannot attain minimum source coverage or training
sample requirements must PASS, not silently fill advanced missingness as zero.
The report includes matched MAE, bias, straight-up accuracy, Brier probability
score and every held-out prediction. It does NOT create synthetic market
lines, totals or player injuries.

IMPORTANT: Date-filtered retrospective provider releases can have revised EPA
values, so these results are NOT true historical published-at-time backtests.
They are a controlled *hypothesis screen* before freezing prospective
challenger predictions. Never promote from retrospective metrics alone.
