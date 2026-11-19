# Injury and roster availability: source-timed picks must not assume team is unchanged

**Research status, November 19, 2026.** Team strength from V04 is season-history dependent; V14 adds opponent matchups, but neither is fully conditioned on the actual expected available roster. The large gap is **athlete-specific replacement value, not lack of visible injury news**. No frozen scoring means, ATS side, total side or player props have been rewritten by this work.

## What the repository already knows
- Source-backed QB history / official current starter reviews / three-deep QB depth labels and prior named passing EPA are implemented in `qb_expected_starters.py`, `qb_passer_history.py`, `qb_conditional_forecast.py` and related research. QB2 rank alone is NOT a scoring penalty; last-game leading passer is NOT confirmed QB1.
- `site_availability.py` captures pregame published, observed and game-matched **official conference** reports for QB, OL, DL/EDGE, RB, WR, TE, LB and the secondary; SOURCE MAY BE MISSING and an unlisted player is never presumed healthy or confirmed active.
- `official_longterm_qb_absences.py` retains three reviewed season-out claims from **Mississippi State and Miami (OH)** with explicit first-eligible source date and replacement confirmation independently. Current manually reviewed long-term registry is **not comprehensive nationwide**. Ohio State's Julian Sayin multiweek injury is documented by the Big Ten's Oct 29 league briefing, but does NOT yet have an official **season-out** university record satisfying this existing strict registry. The current new system must never classify a multiweek prognosis as a documented season-ending absence.
- Existing V03-conditioned QB player EPA / opponent peer, V07 within-team production, and the V04/V14 team scoring models have different evidence/validation. The existence of player-scoring research shadows does NOT establish a validated new V04 injury-adjusted point spread or injury-adjusted total.

## Implemented in this branch

`scripts/site_injury_forecast_gate.py` builds a **game-specific, first-seen, source-timed model eligibility record** after actual official QB/position availability and V14 research scores exist, and before any first pregame website snapshot is frozen. Every upcoming game receives a separate source-identified gate; games that have kicked off are unmodified.

| Condition | Reported forecast usability |
| --- | --- |
| Reviewed university-confirmed QB season absence known by current decision time | `PASS_QB_STATUS_OR_REPLACEMENT_UNRESOLVED`; previous QB team strength not treated as current roster |
| Current QB starter assertion contradicts later official availability | Same `PASS` and `STARTER_IDENTITY_CONFLICT` |
| Official status for a currently expected QB is OUT, DOUBTFUL, questionable, limited etc | Same `PASS` pending verified starter and replacement estimates |
| Official non-QB OL, DL/EDGE, RB, WR, TE, CB, DB, LB, etc OUT / uncertain | `PASS_VERIFIED_NON_QB_EFFECT_UNCALIBRATED`; reported position/player, not assumed starter nor points |
| No actionable verified reports from available sources | `PASS_NO_VALIDATED_PERSONNEL_EFFECT`, with **UNKNOWN is NOT healthy**; no implication of injury-free lineup |
| Player source observed after the decision, game, or player mismatched to fixture | Excluded from this archived decision, cannot be backfilled |

The three output fields `injury_sensitive_ats_action`, `injury_sensitive_total_action`, `injury_sensitive_player_prop_action` are intentionally risk-aware PASS eligibility, not a betting edge, estimate of sportsbook EV or invented prop line. The normal V04/V14 winner, margin, total and player projections remain unchanged and are *not* claimed current-roster-adjusted.

- `site/index.html`: displays a clear **Roster-aware PASS** when current source-backed roster flags exist, with expandable QB/position report status and links to the accepted official source. Ordinary model point projections continue to be labeled explicitly **not injury adjusted**.
- `scripts/site_decision_archive.py`: first pregame archive includes `roster_frozen_forecast_eligibility` separately from V04/V14, validates exact game identity, source publication/observation <= archived decision, not after kickoff, and no model promotion. A new source record cannot change previously archived V04/V14 picks or grades.
- `.github/workflows/cfb-site.yml`: attaches the overlay after conference availability, long-term university QB review and V14 scoring; before website deployment and archive capture.
- Tests: original QB official / availability and V14 baseline + new `tests/test_site_injury_forecast_gate.py`, `tests/test_site_injury_archive.py`, complete regression suite, static site JS syntax check.

## What still has to be built to actually change game-score picks

1. **Source completeness and identity.** Expand official pregame reports across 2026 FBS schools, record first-publication and first-observed time, validate player ID and position, match exact future matchup and upcoming starter role. No source -> mark UNKNOWN. For Ohio State, maintain Sayin vs Fahey *scenario* and independently establish this week's expected starter / report, without converting an old injury into a permanent OUT claim.
2. **Replacement contribution:** for a verified QB change, use *dated, opponent-adjusted* per-QB actual plays, pressure response, expected pass attempts, rushing, explosive and turnover tendencies. Shrink toward comparable players/teams and propagate uncertainty; historical starting role is not inferred solely from team-leading passer. Compare expected points under each available QB and keep defense/team context unchanged. For OL/front/WR/RB/DB, estimate *role and snap usage* before learning an effect; OUT on a backup need not equal OUT on a high-snap starter.
3. **Out-of-sample injury ablation:** freeze V04 and V14 current projected means, an injury-conditioned scoring challenger and verified original pregame source receipts before kickoff. Grade separately on games with verified QB changes, high-snap non-QB absences and no confirmed availability: SU, spread and total MAE, calibrated Brier/CRPS, 80% score intervals and prop-stat accuracy. Use only previously published player reports from original date and prior outcomes, and keep an explicit PASS when effect too uncertain.
4. **Roster-adjusted power rankings:** maintain **two ratings**: full-season historical strength and current expected-roster strength. Never claim Ohio State's season +18.55 V04 rating is a Fahey-only current-strength value unless a separate verified roster-conditioned calculation exists.
5. **No premature promotion.** The 377-game 2026 source already examined repeatedly cannot establish a new independently profitable model; do not assign arbitrary -5/-10 point deductions to injured QB1s. Prospectively validate effect before rewriting the live site scoring engine.

**Result:** Source-backed injury information now changes whether an unconditioned forecast should be **used** for a pick. It does **not yet** change V04/V14's projected points. That latter step requires verified training labels and genuine prospective performance; it is the next modeling milestone, not an unimplemented promise of current behavior.
