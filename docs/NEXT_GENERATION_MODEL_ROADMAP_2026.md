# Next-generation CFB research program — October 30, 2026

## Principles

The five milestones are one connected system. Preserve the live V03 forecast and the
immutable historical records. Forecasts remain `PASS_UNVALIDATED` until they
have independent prospective evidence. Historical PBP publication timing and
the completeness of nationwide injury sourcing are currently **not authenticated**.

## 1. Full-roster availability intelligence — in progress

Existing modules: `injury_history`, `availability_context`,
`personnel_replacement_capture`, `player_replacement`,
`personnel_source_watch`, official personnel source discovery/coverage.

New: `roster_impact_readiness` audits **every position** (QB, RB, WR, TE,
OL, DL, EDGE, LB, CB, DB, S, K, P, OTHER) after each Data Intake capture.
It reports both-sided source coverage and OUT/SUSPENDED versus uncertain
designations by position. An unlisted player is UNKNOWN; a verified report is
not proof of participation or of a complete healthy roster. Crucially, no
number of listed absences is automatically a point adjustment.

Next gates: widen legally usable official school/conference report extraction;
independently crosswalk actual player identity/transfer/position, depth and
dated participation history; match each absence to a learned, shrinkage-
regularized historical replacement effect estimated **only from prior training
games**; validate all-roster, OL/DL and secondary subgroup effects against
identical frozen game cohorts. `player_replacement.train_coefficients` is
a position-count research estimator, **not** verified individual value.

## 2. Evolving team and individual intelligence — partly implemented

Current prior-date team profiles, `team_matchup_intelligence`,
`weekly_profiles`, `qb_defense_adjusted_peer`, QB history and multiple
QB-conditioned shadows exist. Extend to auditable same-source QB rushing,
scrambling, pressure response, turnovers, individual offense and defense
roles, prior-season/transfer priors with explicit sample uncertainty.
Measure trajectory after removing opponent effects and turnover luck; do not
interpret a two-game spike as a verified structural change.

## 3. Advanced matchup interactions — first generation implemented

Current paired opponent-adjusted run/pass, pressure, sack, explosion, red-zone,
drive tempo and turnover research exists. Compare nonlinear/interaction
challengers **one feature family at a time**, using earlier-game-only learned
coefficients and paired chronological folds. Prioritize OL vs pressure/front,
QB pressure response, run reliance vs run defense, and replacement-sensitive
position matchups. PASS for inadequate training/source coverage.

## 4. Game simulation — research engine added, empirical fit outstanding

`game_simulation_research` generates a reproducible **regulation drive
distribution** from explicitly supplied, predecision empirical drive counts,
starting field positions, explosive tags and conditional drive scores.
It reports scores, margins, totals, quantiles and regulation win probabilities.
ATS/O-U estimates are null unless an authentic, predecision market quote is
supplied. This is **not** yet a calibrated full-game model; no audited drive
outcome/field-zone training distribution is plugged in, and the independent
drive assumption omits overtime, possessions shared with pace dynamics and
some non-offensive scoring. Before use, fit from genuinely observed past-only
plays/drives, add correlated possession state and verify proper score-event
attribution; check probability calibration on strictly future games.

## 5. Automated model competition — paired research gate added

Existing `model_shadow_grade`, `candidate_shadow_grade`, and archives already
evaluate several prospective shadows. New `prospective_model_competition`
accepts hash-bound frozen forecasts and independently dated final labels,
refuses mismatches and postkickoff inputs, and grades challenger and reference
on the **same games**. Report paired MAE and bias; do not turn an unpaired
win rate into superiority. This generic evaluator is not connected to the
archive writer yet and cannot promote a candidate by itself. Add authenticated
market baseline comparison, probability calibration, uncertainty estimates,
minimum prospective sample size, and human-reviewed promotion policy.

## Acceptance and operation

1. Full GitHub CI unit tests pass and the scheduled Data Intake produces
   `roster-impact-readiness-<runid>.json` for upcoming games with no live
   score adjustments.
2. New player, game-drive and betting data sources pass historical
   first-availability, confidence and missingness audits.
3. New interaction and simulation versions freeze forecasts before kickoff.
4. Compare V03, recency-corrected control, each challenger and authentic
   observed market benchmarks on identical settled games; record calibration,
   SU, ATS, O/U and log-loss/Brier where probabilities exist.
5. Promotion only after independent prospective improvement, risk/selection
   review and explicit authorization; never rewrite old picks.

**Status:** The audit is operationally integrated. The drive simulator and
generic grader are testable research libraries, **not** live deployed
predictors. None of these changes claims completed player-effect fitting,
accurate nationwide injury status, simulator calibration or a better model.

## Next implementation batch: observed trajectories and advanced matchup board

- `evolving_team_intelligence` accepts independently observed, two-sided game metrics and builds strictly prior-date adjusted team histories; each games' historical opponent baseline must exist. A >=6-game signal is not proof of a structural change and large turnovers are surfaced as a confounder. CLI is available for an independently captured game-history feed; source adapter / first-publication audit is still needed.
- `advanced_matchup_interactions` computes QB-less pressure/pass reliance, offense-versus-defensive run style and explosive passing interactions on the existing time-aware scouting board. Missing inputs remain null; there are no learned weights or active score changes. Data Intake exports this candidate board for independent research and future ablations.
