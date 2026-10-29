# QB starter confirmation and opponent-aware team scouting — October 29, 2026

**Live scoring**: original V03 remains the official website forecast. All newly engineered features and QB scenario changes are **source-labeled research**, not validated betting picks. No historical outcome/backtest is altered.

## QB source coverage: actual blocker versus projections

Most recent full-source measured intake [40966132935](https://github.com/The-Caves/cfb-model/actions/runs/40966132935):

- **230 upcoming team-game slots / 115 games**.
- **206 named expected-starter projections** from live depth chart, observed last-game passer, availability and competing sources; the **other 24 are UNKNOWN**.
- **229/230** team slots have third-party depth charts; **138** of **139** listed school names matched the chart directory. The unmatched remaining team was Merrimack (outside the canonical 138 FBS registry). Third-party QB1/QB2/QB3 ranking is not official confirmation.
- **0** accepted explicit, game-specific, independently reviewed *starter* declarations in the source evidence ledger. The model does **not** claim 206 official confirmations.
- **23** source rank versus recent passer conflicts; **104** unconfirmed slots within 72 hours of kickoff and **4** within 24 hours as of capture. Individual names, review deadlines and source URLs are in `qb-confirmation-review-RUN.csv` and `qb-confirmation-coverage-RUN.json` (same `cfb-qb-role-profiles-RUN` artifact).
- Explicit school/coach statements are not universally published pregame, and an official university preview can describe a **previous-game** return without declaring the next game starter. None should be silently recast as official next-game evidence.
- `scripts/qb_confirmation_coverage.py` creates a timely, auditable source review queue; `scripts/qb_starter_review.py` is the strict reviewed exact-game gate. Projections are already fed into a distinct QB-aware scoring research shadow, with player-conditioned performance even for QB2/QB3 and no fixed backup penalty. An unproven player retains uncertainty.
- Ourlads role snapshots may be stale; recent post-publication observed quarterback usage can override the chart **for a projected starter, not confirmation**.

To increase *actual* confirmed starter coverage, obtain school- or on-record coach-authored dated statements that name who will **start the upcoming specific game**, archive the real publication and observation clocks, require source review and conflict checks. Review queue prioritizes imminent unresolved games. Many will remain **UNKNOWN** until credible sources publish; inventing a confidence label would undermine the project.

## Team style — the information now recorded

From **score-verified two-sided 2026 PBP**, latest six games:
- Separate offensive rushing/pass EPA per play, rush/pass success%, play-calling split and explosive pass/rush tendencies.
- Separate **defensive rushing EPA allowed** and **passing EPA allowed**, and corresponding success/explosive rates from the named opponents' accepted offensive plays (a high positive EPA allowed is **weak defense**, not strength).
- Play-level pressure exposure/opponent pressure generated; red-zone play success, drives and plays per drive when available.
- Source-audited turnovers **committed** and **takeaways**, based on ESPN full-game team boxscores; never guess from the undocumented `turnover_vec` bitfield. Validated **570/570** completed scoreboard games at first collection; unresolved source rows would remain NULL, not healthy or zero.
- Dependence on running: compare scoring performance in *prior games where rushing EPA was nonpositive* versus where positive; only provide conditional gap with at least two observations in each class, describe it as **correlation**, not a causal penalty. A good team can win when its run is stopped.
- Two-way offense/defense matchup observations, plus past-only opponent-strength-adjusted offense and defense residuals, with no same-date result leakage.
- The direct offensive EPA matchup calculation uses **(offensive EPA + opposing defensive EPA allowed)/2**, not an erroneous subtraction: a good offense facing a defense that allows a lot of EPA must get a favorable matchup sign. Defensive negatives correctly suppress offensive outlook. For turnover risks, **(offensive committed turnovers + opposing takeaways)/2** is a *proxy*, not an expected game turnover count.

## Real retrospective test — matched 296 games, 5 weeks

[Research run 40968000342](https://github.com/The-Caves/cfb-model/actions/runs/40968000342), with holdout-game dates strictly after training and real score-verified PBP:

| Variant | Margin MAE | Total MAE | Straight-up |
| --- | ---: | ---: | ---: |
| Original 14-feature V03 baseline within this experiment | **13.793** | **13.6966** | 64.53% |
| Run/pass versus opposing defense only | 13.809 | 13.733 | 64.53% |
| Opponent-adjusted run/pass | 14.337 | 13.809 | 63.51% |
| Turnover risk proxy | **13.744** | 13.755 | **65.20%** |
| Situational alone | 13.742 | 13.730 | 62.16% |
| Everything at once | 15.942 | 16.612 | 62.50% |

The 0.05-point margin MAE gain for the turnover-risk candidate is small and exploratory; totals are slightly **worse**. The overload variant is clearly worse than the 14-input control. The model has experienced home bias, incomplete as-of historical provenance and sparse prospective samples. These historical folds were used during feature development, so no candidate is ready to be promoted based on this alone. A conceptual "defensive battle" is a scenario hypothesis, **not automatic under pick**. Model O/U must be tested empirically and calibrated against independently timestamped market totals.

## Published assets and controls

- `scripts/ingest_advanced.py`: accepted per-side rushing/passing success/play data.
- `scripts/turnover_boxscore.py`: strict independently score/identity validated ESPN turnover capture.
- `scripts/team_matchup_intelligence.py`: team style profile, opponent-adjusted matchup, source coverage and game-disjoint research ablation.
- `scripts/qb_confirmation_coverage.py`: ranked expected versus confirmed QB ledger and imminent-game reviewer worklist.
- `scripts/matchup_profile_archive.py`: content-addressed append-only pregame scouting source for the static site.
- `scripts/site_matchup.py` and `site/index.html`: collapsible matchup scouting on each game card. Scores remain original frozen V03 and show source-time limitations.
- `.github/workflows/cfb-opponent-matchup-eval.yml`: reproducible same-game historical research audit.
- `.github/workflows/cfb-matchup-publish.yml`: publish corrected research scouting to context-state and trigger Pages refresh.
- `.github/workflows/cfb-data-intake.yml`: scheduled capture, starter review queue, score/turnover extraction and research ablations.

The research site at https://the-caves.github.io/cfb-model/ remains on unvalidated V03 **for numeric predictions**. The scouting display is descriptive; it does not alter the score, ATS or O/U selection. The user can open the matchup panel for each game to see team profile strengths/weaknesses and sources.

## Next blocker to clear

1. Review actual source candidates in near-term kickoff order; timestamp explicit, official game-specific starters. Reserve `CONFIRMED` only for accepted dated coach/school evidence; otherwise show `PROJECTED` with confidence and QB1–QB3 rank.
2. Run a truly prospective matched-game test on the new turnover/style forecasts and V03+recency/venue/QB shadows; compare outcome, ATS and OU and sample loss from missingness. Prevent new home-team bias. Consider hierarchical/shrunk opponent adjustments to reduce small-sample overfitting.
3. Train distinct learned QB impact from independent QB1-to-QB2/QB1 return performance across opponent-strength matched samples. The existing player passing-EPA coefficient yields small adjustments and is not proof that it captures full quarterback changes.
