# Next player-prop research milestone: exact team opportunity conservation

October 30, 2026. Research branch only.

`player_prop_team_budget_audit.py` audits available 2026 ESPN-derived
per-game athlete boxes, measuring how often recorded pass completions match
recorded receptions and passing yards match receiving yards. Neither matched
total proves full participation or genuine historical source publication time.
Nonmatched categories are never fixed by inventing zeros.

`player_prop_conserved_opportunities.py` is a standalone **source-gated**
prototype that takes independently verified, already-observed prior team-game
play totals and predecision player-role evidence. It samples same-game
possessions from the existing game-fit model, then assigns team-level pass
attempts, completions, passing/receiving yards, receiving targets/receptions,
and rushing attempts/yards to named conditional players plus preserved OTHER
buckets. Every trial performs exact numerical conservation and rejects
bad source timestamps, corrupt team boxes and claimed full roster coverage
without evidence.

Design choices:
- Per-team pass/rush volume comes from historical observed BOX games, scaled
  by shared simulated possessions, rather than independent player projections.
- Every completed pass has one passer and one receiver; yards go to both.
  This does not mean 1:1 target=attempt is the true football play taxonomy:
  sacks, spikes, throwaways, and scrambles need future validation.
- Every team has explicit OTHER_QB, OTHER_RECEIVER and OTHER_RUSHER buckets
  for players not individually covered by the sourced role evidence.
- Pacing and historical efficiencies are observational research primitives,
  not calibrated pregame expected values.
- This is not yet executable on the scheduled real 2026 slate. It needs
  verified team ID ↔ player roles ↔ exact pre-kickoff opponent lineup/usage
  sources and source-observed previous game budgets. A snapshot taken at
  October 30 must never be used as-if available on an earlier September date.
- No TD attribution or player availability probabilities are yet supported,
  so no usable betting-prop calls are implied.
- Existing V03 picks and prior prediction archives are untouched.

Next: test the above budget conservation on real authenticated completed-game
box totals, then add pregame lineup source coverage and calibration of both
opportunities and efficiency against separately frozen future outcomes.
