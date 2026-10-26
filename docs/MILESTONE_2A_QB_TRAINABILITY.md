# Milestone 2A — game-specific starting-QB model trainability audit

**Audit date:** October 26, 2026.  
**Model currently issuing forecasts:** `V03_RIDGE_OBSERVED_PROSPECTIVE_BASE14_V1` (no QB replacement-value corrections).  
**New readiness tool:** `scripts/qb_trainability_audit.py`; tests `tests/test_qb_trainability_audit.py`.  
**Status:** evidence/readiness infrastructure implemented; **QB replacement effects not trained, not promoted**. `PASS_UNVALIDATED` remains mandatory.

## Grounded data state

Based on the October 26 latest successful [2026 Data Intake run 40252874370](https://github.com/The-Caves/cfb-model/actions/runs/40252874370), using the audited Step 3E one-decision-per-game policy (latest authentic 24–72 hours before kickoff):

| Coverage item | Count |
| --- | ---: |
| Distinct archived ESPN game IDs in research ledger | 113 |
| Games with eligible pregame observations | **53** |
| Archived pregame team-QB slots in those 53 games | **106** |
| Reviewed game-specific confirmed starter slots | **0 / 106** |
| Matchups with verified injury/availability reports on both teams | **9 / 53 (17%)** |
| Games with paired independently observed final scores | **48** |
| Games with original policy observation missing | 60 |
| Sufficient held-out QB evaluation folds | **0** |

The same run reported zero confirmed QB pairs for 61 upcoming game forecasts, in `qb-readiness-40252874370.json`. **Caution:** the 245 individual official QB availability designations available to the October 24 website are conference report *player rows*, not 245 independently confirmed starters. `QB1` on a third-party depth chart is not an explicit game-specific official starting-QB announcement, and a prior game's passer is not proof of this week's starter.

## Why a replacement-value regression is blocked

The Step 3E feature table has 14 team-performance numbers, separate booleans for reviewed QB and covered reports, and verified injury-status *differentials* when both teams' reports exist. It deliberately does **not** contain named player/game-starter identities, first-snap participation, snap counts, game-specific backup/starter switches, or a verified postgame replacement-event label. The only postgame labels are final scores and their observed publication times. An injured QB's prior passer, depth-chart QB2 ranking, or game-point margin is **not** evidence that a replacement was required or how many points a player is worth.

The new script reads the original Step 3E audited quality, pregame feature board and separate postgame labels; verifies exact ESPN identity, clocks, one-record-per-game, signed pregame-to-final evidence chronology and injury-report coverage; reports actual labeled QB slot and injury coverage; and refuses promotion or invented player replacement effects. It explicitly checks that the named starters and independently verified QB replacement events are missing from the current dataset schema. The gate never backfills postgame QB participation into a pregame forecast.

## Predeclared training-readiness criteria

- At least **110** matched as-of pregame/verified final games, with at least **60** games containing confirmed QB1 on **both teams**.
- At least **25** independently verified, differently sourced player-replacement/participation events, with controls/matched comparisons.
- At least **60%** two-sided verified availability-report coverage.
- At least **three chronological folds** and **60 held-out games**, plus historical input source-time attestations and held-out comparison against existing v0.3 baseline.
- If these cannot be met, `ready_to_train_injury_qb_model=false`; no manually assigned 3-, 5-, or 7-point QB effect or false starter designation.

These thresholds are research-readiness gates, **not** guarantees of betting model validation.

## Milestone 2B: actionable next work (official starting-QB confirmations)

1. Begin with exact future ESPN game IDs. Take each school's game-week football notes and dated media/coaching statements from `config/official_athletics_sites_2026.json` and the Milestone 2B official-source discovery inventory, then read the *document-level* statement. Candidate discovered links and depth charts are **not** confirmations.
2. For an explicit this-game confirmation, record exact player, game ID, school, opponent, published timestamp, actual capture timestamp, reviewer timestamp, cited HTTPS source, and a positive unambiguous on-record excerpt in `data/manual/qb_starter_evidence_2026.csv`.
3. Run `scripts/qb_starter_review.py`, `scripts/qb_history.py` and `scripts.personnel_features` with those observations, rejecting conflicting injury/OUT declarations. Current user-visible dashboard can display sourced confirmation without pretending the V03 margin was recomputed.
4. Accumulate actual **postgame** QB starts/participation from independently verified official box scores; label full-game versus first-quarter substitutions separately. Do not backdate later-observed evidence into an older capture, and do not confuse verified postgame appearance with a pregame declaration.
5. After enough prospective matched completed games have accumulated, fit and test `QB_AWARE_CANDIDATE_V1` with correctly point-in-time features, play-style matchup effects and estimated replacements. Compare against the locked V03 baseline and the recency/home-bias candidate on identical eligible game IDs, rejecting overfitting. Do not promote automatically.

## Follow-on Milestone 3

Calibrate totals distributions only after distinguishing past-game EPA/explosive/pace features from authentic original-source timestamps. Maintain separate mean, uncertainty and tail calibration; compare every experiment with both the current total model and contemporary market line on one game ID each. QB effects and weather must remain unknown unless independently observed before decision.

*Free GitHub Actions/context-state infrastructure; no new AWS/paid API dependency.*
