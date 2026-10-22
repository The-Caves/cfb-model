# v0.4 Step 2: actual pregame capture-time evidence

The scripts/pregame_evidence.py module runs only after current ESPN, SportsDataverse and upcoming matchup ingestion. For each FBS game with a future kickoff, it reconstructs the team profiles from games completed on earlier Eastern football calendar dates, and freezes the profiles plus their observed capture time, ESPN game identity, kickoff time, SHA-256 hashes of source files, original provider PBP digest and collection timestamps.

The get_asof_feature gate refuses an observation captured after the requested historical decision time or one used at/after kickoff, rejects future source retrieval timestamps, and checks the profile checksum. Missing, noncanonical and already-started games are quarantined. Each workflow run writes one capture-<run-id>.json using exclusive-create file mode. The public repo contains code and tests, not source data.

**Status: PASS_UNVALIDATED.** A future game's captured profile now records what our workflow actually knew at collection time, but this does not verify old provider publication dates or the authenticity of data retrospectively revised before our capture. Archives currently live in GitHub Actions artifacts retained 30 days; durable immutable storage and independent validation of the workflow receipt are still required. Historical September profiles reconstructed in October must NEVER be upgraded to verified pregame observations. No real FanDuel prices or QB/injury replacement adjustments are included.

## Verified live workflow checkpoint — October 21, 2026 EDT

[Actions run 39705289431](https://github.com/The-Caves/cfb-model/actions/runs/39705289431) completed successfully with **270 passed tests**, successful full ESPN/advanced/context ingestion, the new Step 2 observation capture, and artifact upload. The 30-day artifact `cfb-2026-data-39705289431` contains `pregame_evidence/capture-39705289431.json`.

The record has **108 eligible future FBS games**, capture UTC `2026-10-22T01:25:56.094528+00:00`, six input-file SHA-256 hashes and stored profile hashes verified for every accepted game. The evidence capture JSON is 202,040 bytes; SHA-256: `fc0e68d38d8d587de0e294001ba048678c23f191e64602f59e765b1dfe005255` (verify against the downloaded Actions artifact). Stored observed source times all precede the capture instant. No claim is made about independent timestamp attestation, durable storage or original historical publication times.

**Next gate:** private append-only durable retention and independently verifiable provenance receipts for future captures. Only then should the model use these real observed records in genuine source-time-restricted walk-forward experiments. Historical September weeks reconstructed from the October release must remain unverified.
