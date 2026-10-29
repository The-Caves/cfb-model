# October 29 — QB-aware + light travel shadow implementation

## Requested modeling behavior

- Travel is a modest modifier, **not a second home-team bonus**. The independent venue/travel model estimates neutral team strength and home venue separately, and its travel coefficient is shrunk to 25% and capped at **±1.25 points per game**. Missing time zones, recent rest, coordinates or historical coverage remain **unknown**, not a fabricated zero-mile trip. The cap is a research design, not a learned or validated effect size.
- Starting quarterback: Collect an **expected** QB from an observed 2026 third-party depth chart, previous-game passing participation and, if present, explicit official gameweek starter confirmation. Preserve QB1/QB2/QB3 chart **rank** separately from who is projected to start. Detect contradictions and favor explicit, reviewed source over page ranking. An officially OUT QB1 plus evidence of a recently played QB2 may produce a medium-confidence, unconfirmed QB2 projection; otherwise emit alternate QB scenarios rather than manufacturing a certainty.
- Numerical QB scenarios: use each named passer’s **prior** pass EPA per pass-tagged play relative to the team pooled passing form. Pass the difference through the **already trained V03 passing-EPA coefficient**; shrink noisy samples toward the prior team profile and cap each individual conditional scenario at ±4 margin points. A QB2 can improve the team's predicted scoring; QB1 isn't presumed better, and a QB with no meaningful prior play **does not get an automatic penalty**. All candidate adjustments are **research-only, source-identified, uncalibrated**, and not automatically promoted to the live model.

## Data flow

1. After completed-game ingestion, `qb_passer_game_history_2026.csv` retains observed player pass plays from accepted PBP and the receipt timestamp.
2. `qb_role_features.py` records previous-game leader and season leader **proxies** (never confirmed starters) and observed official prior-game return context.
3. `qb_expected_starters.py` fetches current ranked depth charts for upcoming teams; aligns them to the exact game, recent passer, game-specific QB availability and confirmed starting source. Saves each team's expected starter confidence, chart rank, alternatives and all missingness to an inspectable archive. External website coverage is not equivalent to confirmed starter coverage.
4. After freezing original Step3G baseline and four earlier shadows, `qb_conditional_forecast.py` saves per-QB passing form and **conditional scoring predictions** to a fifth independent research artifact. Original V03 rows remain unmodified.
5. `city_timezone_refresh.py` enriches historical site coordinates with verified IANA zones. `venue_travel_history.py` calculates retrospectively reconstructed travel features from preceding game venues and verified source cities.
6. `venue_travel_forecast.py` freezes a separate prospective neutral-field venue and travel research candidate. The travel model has an 80-game minimum historical sourced cohort and a very small capped point effect. No raw travel-induced point adjustment is assumed.

## Remaining source limitations and next tests

- Historical provider PBP, game venues, and historical depth charts can be revised and do not prove what was published at a past pregame decision instant. Prospective data sources are captured now and archived for future testing. We do not claim lookback accuracy validates the prospective model.
- Official confirmed game-specific QB starts are still sparse. Depth-chart QB1 is a **position**, not evidence the named player will start Saturday. Press notes, availability updates, and last-game passer disagreements should produce explicit uncertainty rather than a fabricated fact.
- Measure expected-starter/source coverage, QB passing sample availability, and effect of expected vs alternate QBs for *every upcoming game*; investigate missing ranks, malformed chart pages, and source outages; retain disabled alternatives.
- Grade the new venue, QB and V03/recency predictions on identical independent pre-kickoff games for SU, margin MAE, bias and source-availability cohorts before any promotion. No fake sportsbook odds. Missing expected QBs should be PASS not an assumed healthy QB1.
- No change to the public website's live V03 picks as a result of this research commit.

This document was committed with `[run-intake]` to force a **real** immediate data intake and audit run rather than counting unit tests as end-to-end source verification.

## October 29 integration hardening

- Prospectively generated QB1/QB2/QB3 scenarios now include **individual projected margin values** rather than only labels.
- Confirmed starting quarterbacks still require source reviews. A last-game player who appeared **after** a stale depth chart's update becomes a *projected recent passer* instead of being overwritten by stale QB1; named-player initials are normalized to match PBP.
- Forecast scripts now load the real Step3G immutable `record` envelope, not a bare JSON object.
- Experimental QB and venue/travel forecast records are additionally persisted to an append-only GitHub archive with exact baseline source identity; models remain nonpromoted.
- Run-intake tag on this docs commit triggers the repaired full pipeline and source-coverage audit.
