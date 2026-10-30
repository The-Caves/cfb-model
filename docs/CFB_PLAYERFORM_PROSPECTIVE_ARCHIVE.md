# PlayerForm R1 prospective player-stat research archive

**Purpose:** stop reconstructing an earlier model prediction after knowing the
final player yardage. This is a legitimate first step toward independently
measurable future player-stat and, eventually, player-prop calibration.

During each successful public site build, before kickoff, a *separate archive
job* saves exactly the displayed PlayerForm R1 conditional passing, rushing
and receiving yardage projections to the existing private workflow's
`context-state` branch (not to the public Pages site and not committed as
production model coefficients). Files:

- `research_2026/player_projection_snapshots/YYYY/MM/DD/run-NNN.json.gz`
- `research_2026/player_projection_snapshots/index.json`

These are append-only, checksum-indexed, duplicate/rewrite protected.
One record identifies the ESPN game/athlete, statistic, model version,
observed before-kickoff projection value, official reported status,
observed workload role share (if any), V03 original forecast digest,
score model version, and the distinct source publication/capture times.

The research forecast is **conditional on player involvement** and not a
probabilistic or book-quoted player prop. No player is assumed healthy merely
because they were in a prior box. Snapshot creation never changes V03
frozen scores, ATS/totals or the separate sportsbook snapshot archive.
A GitHub commit/archive timestamp does not authenticate the original
publication instant of revised historical ESPN box rows.

**Future acceptance test:** settle each player-stat line against an
independently captured official player-game box after the game, keeping
unknowns and DNP/unobserved categories UNGRADED. Choose a policy for
earliest eligible captured per-player/game/metric projection; never cherry
pick postgame archived forecasts. Grade mean absolute error on matched
cohorts, coverage, uncertainty and calibrated probability intervals before
promoting PlayerForm and adding any bookmaker prop comparisons.
