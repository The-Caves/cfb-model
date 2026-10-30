# New player/drive source readiness — October 30, 2026

SportsDataverse's freely published football release catalog lists ESPN season
rosters, 2026 player targets/touches, defense tackle shares, and raw drives.
\`scripts/nextgen_source_readiness.py\` captures timestamp, checksum, schema,
row-count and failure reason for **only five** predefined 2025/2026 sources.

A row in a season roster is *not* a game-specific starter; \`target_share\`,
\`touch_share\` and \`tackle_share\` measure opportunities, NOT snap share.
Season aggregates can include information from after a hypothetical historical
game; NEVER use today's release to predict September retrospectively.
A drive labeled TD may belong to a defensive return; no source-provided code
may be reinterpreted as verified offensive scoring until independently
reconciled to the official score progression.

Source evidence can inform future roles/expected participation **only if the
source was actually observed pre-kickoff and has stable player/team IDs**. The
absence of a source file or unlisted injury is UNKNOWN, not healthy.
The probe generates **no picks and no injury effect**. It gives an actionable,
honest readiness report for the next source-adapter work.

References:
https://py.sportsdataverse.org/docs/cfb/reference/loaders/usage
https://py.sportsdataverse.org/docs/cfb/reference/loaders/rosters
https://py.sportsdataverse.org/docs/cfb/reference/loaders/other
