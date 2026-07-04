# Market Signals

Use a market signals JSON file when odds or prediction-market prices should calibrate the forecast.

## Match Markets

Each row in `matches` describes one match. Use either explicit team probability fields:

```json
{
  "team1": "Paraguay",
  "team2": "France",
  "team1_probability": 0.075,
  "team2_probability": 0.925,
  "source": "Polymarket",
  "volume": 25000,
  "liquidity": 12000,
  "spread": 0.02,
  "updated_at": "2026-07-04T09:55:52Z"
}
```

Or a team-keyed probability map:

```json
{
  "probabilities": {
    "Paraguay": 0.075,
    "France": 0.925
  },
  "source": "Polymarket"
}
```

The script normalizes probabilities if they do not sum exactly to `1.0`.

## Champion Futures

Each row in `futures` can calibrate champion probabilities:

```json
{
  "rank_type": "champion",
  "team": "France",
  "probability": 0.32,
  "source": "Public sportsbook odds snapshot",
  "volume": 50000,
  "liquidity": 25000,
  "spread": 0.03
}
```

Futures rows are normalized across the supplied teams. If the supplied futures cover less than 50% total raw probability, the script skips the futures blend and emits a warning.

## Quality Fields

Market signal weight starts from `--market-weight` and is capped at `0.65`.

- `volume < 1000` reduces weight.
- `liquidity < 500` reduces weight.
- `spread > 0.08` reduces weight.
- `spread > 0.15` reduces weight more aggressively.
- Explicit `weight` on a row overrides the default before quality adjustments.

Use lower weights for stale, low-liquidity, or unclear sources. Use higher weights only for recent, liquid markets whose outcomes map cleanly to the match or futures question.
