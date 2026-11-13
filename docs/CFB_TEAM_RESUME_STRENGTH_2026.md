# 2026 opponent résumé strengths: SOS, SOV, SOR

## Research-only, earlier-date team profiles

The source-gated research module \`scripts/team_resume_strength.py\` now computes the following *explicit* team profile fields from original ESPN final games, as observed today but filtered to games with an Eastern football date strictly before a chosen cutoff:

- **SOS:** mean strength (points) of opponents actually played, using a conservative score-based opponent-adjusted rating fitted on the same earlier-game slate; also reports average 0-rated team's expected win percentage versus that exact schedule and home/away/neutral venue.
- **SOV:** mean opponent-strength (points) of teams beaten; and historical W/L win rate of defeated opponents at the same cutoff. It is **null**, not zero, for teams without wins.
- **SOR (research analogue):** \`-log10(P[0-rated average team wins >= this many games against those exact opponents at those exact historical venues])\`. Compute the Poisson-binomial tail over opponents. Smaller tail probability (larger rarity score) means a record is less plausible for an average team, distinct from raw team win percentage. **This is not ESPN's proprietary official SOR statistic.**
- Record vs schedule: actual wins minus expected wins of that reference 0-rated team; opponent-adjusted team power, last-four record and last-four strength of schedule are also available.
- All metrics carry \`cutoff_date_exclusive\`, source game IDs, prior game count and \`historical_publication_verified: false\`. Raw historical source first-publication times are unverified; retrospective backtest use must say so. No opponent missingness is fabricated.

This is intentionally a **diagnostic research feature**. It does not yet alter V04 scoring, the V10 possession simulator, published PRESSBOX picks or prior grades. SOS, SOV and SOR are correlated with V04's existing opponent-adjusted team power, so injecting each as a new fixed score multiplier would double-count strength and risk overfitting. Integrate them as a *separately graded, bounded and regularized V10 challenger*, trained on older football weeks, only after validating their added value over the common opponent-adjusted V04 score prior.

**Other V10 team profile features presently consumed:** V04's opponent-aware offensive and defensive score ratings, recency-weighted EPA (total/pass/rush), prior pass/run share, pressure, pass/run success when backed by denominators, red-zone *play* success (not genuine touchdown/trip), explosive plays, verified prior turnovers, starting field position, prior possession count and defensive return TDs. It does **not** fully consume QB lineup, injuries, game-weather conditioning, offensive-line/defensive-front personnel, and detailed down-distance clock state. UI scouting includes more information than scored-feature coverage.

The CFB team-only route and this workflow do not import data from other repositories. 
