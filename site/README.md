# CFB dashboard deployment and data contract

The static site lives in `site/index.html`. It is not deployed yet.

## Private preview

Do not enable GitHub Pages or publicly deploy this directory while the dashboard is intended to remain private. GitHub repository privacy is not the same as website access control. For an authenticated preview, connect the repository to a hosting provider with access controls, verify those controls on the actual deployment, and only then distribute the preview URL. No hosting account or domain has been connected by this commit.

## Published data

The site optionally loads `site/data/dashboard.json` using a relative path. A missing file is a valid initial state: no picks are shown. When the exporter is implemented, publish a JSON object:

```json
{
  "schema_version": 1,
  "generated_at_utc": "2026-10-23T14:00:00Z",
  "games": [
    {
      "game_id": "example-only",
      "away_team": "Away",
      "home_team": "Home",
      "kickoff_utc": "2026-10-24T19:00:00Z",
      "model_home_margin": null,
      "model_total": null,
      "market_home_spread": null
    }
  ],
  "prospective_records": {
    "su": {"wins": 0, "losses": 0, "pushes": 0},
    "ats": {"wins": 0, "losses": 0, "pushes": 0},
    "ou": {"wins": 0, "losses": 0, "pushes": 0}
  }
}
```

The example is a schema illustration, not a prediction or betting line. Positive `model_home_margin` means the home team is projected to win by that many points; negative `market_home_spread` means the home team is favored. Home ATS edge = model home margin + market home spread.

## Validation rules

- Store market line source, quote timestamp (UTC), collection timestamp (UTC), game ID, and kickoff timestamp.
- Freeze the prediction and market snapshot before kickoff; never retroactively overwrite a frozen prediction.
- If no verified pregame market quote exists, show ATS edge as unavailable and do not grade ATS.
- Grade pushes separately and exclude them from ATS win-rate denominator.
- Grade straight-up, ATS and totals from the same archived snapshot with explicit as-of times.
- Keep retrospective research metrics separate from prospective performance.
- Do not promote experimental model variants solely based on historical holdouts.
- Avoid publishing user identifiers or private personnel/news evidence in static artifacts.
