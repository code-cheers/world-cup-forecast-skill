---
name: world-cup-forecast-skill
description: Fetch and forecast FIFA Men's World Cup data with free-first public sources. Use when Codex needs to answer Chinese or English requests such as 预测世界杯排名, 世界杯下一轮预测, 世界杯冠亚军, 世界杯球员进球数, World Cup forecast, World Cup historical rankings, World Cup top scorers, next-round prediction, or final ranking prediction.
---

# World Cup Forecast

## Overview

Use this skill to fetch historical FIFA Men's World Cup rankings, summarize the current tournament state, aggregate current-tournament scorers, and produce transparent heuristic forecasts for upcoming matches or final rankings. When odds or prediction-market data is available, blend it as a market calibration layer instead of replacing the underlying model.

Prefer the bundled CLI for repeatable data fetching and simulation:

```bash
python scripts/worldcup_forecast.py history --since 1926 --positions 4 --format markdown
python scripts/worldcup_forecast.py current --season 2026 --format markdown
python scripts/worldcup_forecast.py predict --season 2026 --target next-round --format markdown
python scripts/worldcup_forecast.py predict --season 2026 --target final --runs 2000 --format markdown
python scripts/worldcup_forecast.py predict --season 2026 --target next-round --market-signals-file examples/market-signals.example.json --format markdown
python scripts/generate_daily_report.py --season 2026 --runs 5000
```

Markdown output defaults to Chinese and should be table-first: summaries, predictions, scorers, group tables, and final ranking probabilities should be presented primarily as Markdown tables. Chinese Markdown output should display common country/team names in Chinese, such as `阿根廷` instead of `Argentina`; use `--lang en` for English Markdown output and `--lang zh` to be explicit. Use `--format json` when the result needs further processing; JSON keys stay stable regardless of `--lang`. Use `--seed` with `predict --target final` when reproducibility matters.

Public ratings:

- Elo ratings are enabled by default from public World Football Elo pages. Use `--no-elo` to disable them.
- FIFA rankings are available with `--use-fifa-ranking`; this is slower because the script fetches FIFA team ranking pages per tournament team.
- Use `--elo-url` or `--fifa-url-template` only when the public page structure or mirror changes.

Market signals:

- Use `--market-signals-file <path>` with JSON odds or prediction-market probabilities when available.
- Use `--market-weight` to control the default blend weight. Keep ordinary markets around `0.30-0.45`; only raise weight for recent, liquid, low-spread markets.
- Keep market signals optional so the skill still runs from free public data when no odds source is configured.

English examples:

```bash
python scripts/worldcup_forecast.py current --season 2026 --format markdown --lang en
python scripts/worldcup_forecast.py predict --season 2026 --target final --runs 2000 --format markdown --lang en
```

## Workflow

1. Identify the user's target:
   - Historical champions, runners-up, or top-four rankings: run `history`.
   - Current tables, completed matches, and scorer counts: run `current`.
   - Next unplayed round or match probabilities: run `predict --target next-round`.
   - Tournament winner, runner-up, third, and fourth probabilities: run `predict --target final`.
2. Decide whether the answer should include market calibration:
   - If no reliable odds or prediction-market snapshot is available, run without `--market-signals-file`.
   - If a market snapshot is available, normalize it into the JSON schema shown in `examples/market-signals.example.json` and pass `--market-signals-file`.
3. Run the CLI from this skill directory or pass the full path to `scripts/worldcup_forecast.py`.
4. Prefer table-first Markdown in the final answer. Avoid joining team names and venues without a separator; keep date, matchup, group, and venue in separate table columns.
5. Match the user's language. For Chinese requests, omit `--lang` or pass `--lang zh`; for English requests, pass `--lang en`.
6. State that v1 is free-first and refresh-on-run, not second-by-second live tracking.
7. If using market signals, distinguish `模型` / `市场` / `融合` probabilities and call out disagreement games as lower-confidence.

## Data Source Guidance

Read `references/data-sources.md` when changing source URLs, debugging data availability, or explaining why some live player/event fields are unavailable without an API key.

Default sources:

- OpenFootball `worldcup.json` for current fixtures, results, and listed scorers.
- Fjelstul World Cup Database CSVs for historical final rankings and historical strength.
- World Football Elo public pages for current national-team strength; enabled by default.
- FIFA/Coca-Cola Men's World Ranking team pages for optional official rank and points; enable with `--use-fifa-ranking`.
- Optional market signals file for Polymarket, sportsbook odds, or manually curated market snapshots.

If a user asks for live lineups, xG, shots, odds, momentum, or full player match stats, explain that those fields usually require a keyed provider and ask for credentials or provider preference before extending the script.

## Forecast Guidance

Read `references/forecast-method.md` when modifying or explaining the prediction model.

Always describe outputs as heuristic forecasts, not betting advice or guaranteed outcomes. Mention the main signals: public Elo, optional FIFA ranking, current points, goal difference, goals scored, current scorer impact, recent form, host boost, and historical top-four strength.

When market data is present, describe the full evidence stack:

1. Tournament facts: fixtures, completed scores, group tables, top scorers.
2. Fundamental model: Elo/FIFA, historical top-four strength, current form, goals, host boost.
3. Market calibration: prediction-market prices or sportsbook odds adjusted by freshness, volume, liquidity, and spread.

Use market data to calibrate probabilities, not to silently override the model. A market with low liquidity, wide spread, stale timestamp, or unclear source should receive lower weight or be reported separately.

When a user asks for 冠亚季军, 冠亚军, podium, or top-three forecasts, prefer the `最可能冠亚季军组合` / `Most Likely Podiums` table from `predict --target final`. Do not create a podium by taking the top marginal team from the champion, runner-up, and third-place sections independently; that can produce impossible duplicate teams.

For knockout placeholders, let the script resolve the bracket. If placeholders remain unresolved in a next-round forecast, report them as unresolved rather than guessing teams manually.

## Daily GitHub Report

Use `scripts/generate_daily_report.py` to write a report into `forecasts/`:

```bash
python scripts/generate_daily_report.py --season 2026 --runs 5000
```

The repository includes `.github/workflows/daily-world-cup-forecast.yml`, scheduled for 08:00 Asia/Shanghai. The workflow generates `forecasts/latest.md` and `forecasts/daily/YYYY-MM-DD.md`, then commits them back to GitHub.

This daily report does not require Codex cloud or an OpenAI API key because the forecast is produced by the deterministic local CLI. If the report should include Codex-written narrative analysis, use the Codex GitHub Action or a Codex automation as a later layer.
