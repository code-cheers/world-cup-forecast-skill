# Data Sources

Use these sources in free-first mode. Verify live availability before relying on exact current results.

## OpenFootball worldcup.json

- URL template: `https://raw.githubusercontent.com/openfootball/worldcup.json/master/{season}/worldcup.json`
- Best for current tournament fixtures, completed scores, group labels, venues, and listed scorers in completed matches.
- The 2026 file contains scheduled group-stage matches and knockout placeholders such as `1A`, `2C`, `3C/D/F/G/H`, `W89`, and `L101`.
- This source is public-domain data and does not require an API key.

## Fjelstul World Cup Database

- Base URL: `https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv`
- Use `tournament_standings.csv` for historical final top-four rankings.
- Use `goals.csv` when a user asks for historical goal records beyond the current tournament.
- Use `teams.csv` to map current team names to FIFA country codes when optional FIFA rankings are enabled.
- The script fetches `tournament_standings.csv` for historical strength and ranking summaries.
- Filter historical rows to `FIFA Men's World Cup`. The database also includes women's tournaments, and mixing them into men's forecasts will badly overrate teams such as the United States.

## World Football Elo

- URL template: `https://www.international-football.net/elo-ratings-table?year={year}&month={month:02d}&day={day:02d}`
- Best for no-key current national-team strength. This is enabled by default for `current` and `predict`.
- The parser reads the public Elo table for the current system date. Use `--elo-url` if the user needs a specific date or a mirror.

## FIFA/Coca-Cola Men's World Ranking

- URL template: `https://inside.fifa.com/fifa-world-ranking/{code}?gender=men`
- Best for official FIFA rank and points. Enable with `--use-fifa-ranking`.
- This source is slower because the script fetches one official team page per tournament team code, then reads the embedded ranking JSON.
- Keep FIFA rankings optional so ordinary forecasts remain fast and no-key.

## Market Signals JSON

- CLI flag: `--market-signals-file <path>`
- Best for prediction-market prices, sportsbook-implied probabilities, or manually curated odds snapshots.
- The script does not require a live paid odds provider. Convert any available market data into the schema shown in `examples/market-signals.example.json`.
- Match markets can include `team1_probability`, `team2_probability`, optional `draw_probability`, `volume`, `liquidity`, `spread`, `source`, and `updated_at`.
- Champion futures can include `rank_type: "champion"`, `team`, `probability`, and the same quality fields.
- Market weights are capped and quality-adjusted. Low volume, low liquidity, or wide spread reduce the effective blend weight.

## Optional Paid/Keyed Providers

Do not require paid providers in v1. If a user asks for true live event feeds, lineups, player match stats, xG, odds, or attack momentum, explain that free public data may be incomplete and ask for an API key or provider preference.

Known extension candidates:

- BALLDONTLIE FIFA World Cup API: covers 2018, 2022, and 2026 with teams, standings, matches, rosters, events, player match stats, shots, momentum, and odds. Most rich endpoints require an API key and paid tier.
- API-FOOTBALL or Sportmonks: use only when the user has credentials or explicitly chooses that provider.
- Polymarket or sportsbook feeds: useful for market calibration when the data includes clear timestamps, prices, liquidity, and source attribution.
