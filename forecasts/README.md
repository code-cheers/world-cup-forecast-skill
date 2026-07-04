# Forecast Reports

Daily generated reports are written here by `.github/workflows/daily-world-cup-forecast.yml`.

- `latest.md` contains the newest generated report.
- `daily/YYYY-MM-DD.md` contains dated snapshots.

The workflow runs at 08:00 Asia/Shanghai using GitHub Actions. Reports are generated from public tournament data, the transparent heuristic model, and optional market signals when a market JSON file is provided.
