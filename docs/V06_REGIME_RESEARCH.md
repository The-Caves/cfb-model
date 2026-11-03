# V06 research — detecting a sustained change in team quality

**Status: research only.** This does not override V04 website scores, V05 shadow scores, frozen predictions, or the V04 ATS PASS policy.

## Problem

A preseason or full-season team profile can overstate a team whose offensive efficiency fell after a quarterback change. A team can also have an unusual game decided by late turnovers or special-teams scores. Neither the user's narrative nor coaching news should automatically change the score.

## Experiment

`scripts/v06_regime_shift.py` fits from source-matched **completed 2026 games before the forecast Eastern football day**. For each team it computes opponent-adjusted scoring margin, scoring offense, and defensive suppression, comparing the last **three** results with the four immediately preceding. Both windows use medians to suppress one outlier, and all three recent games must support the directional change. Deviations below four points are ignored; larger changes are shrunk and bounded to avoid unsupported rating jumps. Thin-history teams get zero adjustment.

Four fixed variants are evaluated on exactly the same held-out game IDs: full scoring+margin change, no change, margin only, scoring only. The baseline is V05 without the existing form adjustment, avoiding double-counting that feature. **No verified QB identity, coach dismissal, injury news, bookmaker line, or betting result is used to fit V06.** A separate verified personnel component is still needed.

## Initial 2026 results

301 matched games across five chronological folds (historical source-publication times not fully authenticated). Only **13 matchups** had seven prior games for both teams at their forecast cutoffs.

| Variant | SU accuracy | Margin MAE | Total MAE |
|---|---:|---:|---:|
| V04 | 66.78% | 13.2053 | 13.4801 |
| V05 full | 65.45% | 13.3458 | 13.3216 |
| V05 no form (V06 base) | 64.78% | 13.4119 | 13.4272 |
| V06 full | 65.45% | 13.3857 | 13.3974 |
| V06 margin only | 64.78% | 13.4198 | 13.4272 |
| V06 scoring only | 65.78% | 13.3779 | 13.3974 |

V06 slightly helps over its no-form baseline, but remains behind V05 full on totals and V04 on margins. **Not promotable; insufficient regime-active sample.** No ATS advantage is claimed.

## Next evidence-dependent milestone

A verified official university/league QB availability signal, a separately recorded first-observed timestamp, and a measured replacement-value method with previous backup game data are needed to recognize a season-ending QB injury without inventing an arbitrary point penalty. Protect previously frozen forecasts from hindsight. Reassess sustained score decline on subsequent *prospectively archived* games and decline to apply it if it fails.
