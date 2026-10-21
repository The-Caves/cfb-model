# Step 4 handoff: 2026 pregame context and player availability

Last edited: 2026-10-21. Public repository documentation — no account or personal details.

## Scope and validation boundaries

- ESPN 2026 schedules/results, rest, weather and approximate travel are collected with source timestamps and explicit coverage gaps.
- SEC, Big Ten, ACC and Big 12 publisher cards provide player **availability**, not medical diagnoses or independently confirmed quarterback starters.
- Timestamped context snapshots, changes and the final observed pre-kickoff freeze live on the `context-state` branch.
- `scripts/qb_starter_review.py` only admits approved game-specific official evidence. No actual game-start claims are preloaded; the default CSV is header-only.
- `scripts/qb_official_news_watch.py` checks five official football RSS feeds for research leads. Headline candidates always remain `UNREVIEWED_NEWS_CANDIDATE`, never `QB_STARTER`.
- `scripts/qb_review_queue.py` builds per-game/per-team review records from the prospective context and news candidates. It distinguishes missing coverage, observed availability, research headlines and separate confirmed starter evidence.
- `scripts/qb_review_archive.py` validates timing, game identity, consistency and non-promotion of news before publishing to `context-state/state/qb_review_latest.json` and dated immutable compressed history. An invalid/missing required queue causes a workflow failure instead of false confirmation.

## Verification checklist

1. Check current `main` HEAD and recent [CFB Pregame Context Delta](https://github.com/The-Caves/cfb-model/actions/workflows/cfb-context-refresh.yml) runs.
2. Confirm CI validation and the **full** context refresh succeeded on the current commit (a code-only CI pass is not live source verification).
3. Inspect `context-state/state/summary.json` for `qb_review`, plus `state/qb_review_latest.json`. Compare run ID and timestamps; a past successful run does not prove future sources remain healthy.
4. Verify the two team-game records for every upcoming match, no unexpected confirmed QB assertions, explicit `NOT_CONFIGURED`/fetch failures, and research-only candidate statuses.
5. Review actual official material before promoting any QB claim through `data/manual/qb_starter_evidence_2026.csv`. Do not invent an opponent, publication timestamp, QB replacement or effect size.
6. Preserve `PASS_UNVALIDATED`: sportsbook market integration, historical odds/prior training, replacement-value validation, and chronological SU/ATS/O-U backtesting remain separate steps.

## Operational limitations

This is a limited five-school **news discovery** pilot, not national confirmed-starter coverage. Schools do not publish announcements uniformly. Absence of a headline or report is missing information, never proof that a QB is available or will start. Open-Meteo forecasts and straight-line travel estimates are prospective proxies, not hindsight-proof historical betting features. GitHub Actions scheduling can be delayed.

The README and `docs/CONTEXT_DELTA.md` carry current architecture and safe continuation guidance. This handoff contains only public code paths, runbooks and research conventions.

## Step 4 completion threshold and feed additions (2026-10-21)

Successful [full cloud run 39651180891](https://github.com/The-Caves/cfb-model/actions/runs/39651180891) verified the new `qb_review` totals written into `context-state/state/summary.json`: 218 team-game slots across 109 upcoming games, 9 team-game slots with a fetched official athletics feed, 209 unconfigured slots, 4 team-game slots with QB availability signals, and zero confirmed QB starter records. Archived review data are available in `state/qb_review_latest.json`. This establishes actual workflow persistence, not merely code-unit-test success.

The official athletics news-feed registry has been expanded from five to seven with football-specific URLs listed directly by [Texas Athletics](https://texaslonghorns.com/rss_feeds) and [North Carolina Athletics](https://goheels.com/rss_feeds). Feed download and XML parsing must be validated in GitHub Actions on the expanded code. A configured feed does not establish player availability or starting-QB certainty.

**Proceed to Step 5** after a successful full refresh under the expanded registry. Step 4's operating service is source-audited and can express unknown coverage; comprehensive nationwide starter announcements and empirically validated QB replacement values remain open research dependencies, not falsely completed features. Step 5 builds timestamped historical/live market spreads, totals and prices, then checks leakage-free joined snapshots.
