# Official long-term QB absences — source-first milestone

This is a **risk-aware research overlay**, not an automatic change to V04 or V05 team scoring. Football narratives or coaching events cannot change the model absent measurable and timestamped inputs.

## First official-source regression

Mississippi State's university issued an official October 27, 2026 statement that QB Kamario Taylor would miss the remainder of the season. The source is recorded at:
https://hailstate.com/news/2026/10/27/football-statements-on-status-of-quarterback-kamario-taylor

The registry in `data/context/official_longterm_qb_absences_2026.json` deliberately sets **November 4, 2026, 00:00 UTC** as the *earliest model-use time*. This is an embargo after the November 3 source review. The October 31 Texas game and all previously frozen pregame forecasts remain unchanged; this fact must never be planted into earlier historical picks as though the system captured it on October 27.

## How the safeguard works

- The university article is reviewed and stored with a verified publisher hostname, team, named QB, injury designation and publication date.
- Only future 2026 fixtures after the first-use time can carry the official long-term absence. The old V03 forecast and V04/V05 point predictions are never rewritten.
- A separate already-reviewed official **replacement starter** can be recognized without treating a depth-chart entry, prior passing leader, or the injury statement as confirmation of the substitute.
- If the QB is officially ruled out and the replacement starter remains unverified, V04's ATS and over/under research policy explicitly **PASSes** instead of applying an invented points deduction. Both the source and PASS are frozen in the pre-kickoff archive and validated in the performance grader. The UI shows a link to the university announcement.
- This first record does not claim full school coverage. Future source records must be individually university verified, and all retrospective data must honor observation timestamps.

## Still missing

A calibrated QB-player replacement component must compare verified starter / substitute identities, prior and transfer performance, offensive-line context, and genuinely time-correct earlier-game results. The project currently does not have sufficient authenticated QB coverage to claim a causal points-per-game impact.

No stronger betting-performance claim follows from the new PASS rule. It only reduces unsupported predictions on games where a season-ending quarterback absence is known but unquantified.
