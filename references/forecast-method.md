# Forecast Method

The bundled script uses a transparent heuristic, not a trained betting model. Present outputs as directional forecasts.

## Team Rating

Each team starts from a neutral rating and receives these adjustments:

- Historical men's top-four strength from `tournament_standings.csv`, filtered to `FIFA Men's World Cup`, weighted by finish and recency.
- Public Elo rating adjustment from World Football Elo pages, enabled by default.
- Optional FIFA ranking and points adjustment when `--use-fifa-ranking` is supplied.
- Current tournament points per match.
- Current tournament goal difference per match.
- Current tournament goals scored per match.
- Recent current-tournament points from the last three matches.
- Current tournament scorer impact from completed-match goal totals.
- Host boost for Canada, Mexico, and United States in 2026.
- Optional market calibration from odds or prediction-market probabilities.

Current-tournament signals are sample-weighted. Before a team has completed all three group matches, points per match, goal difference, goals scored, recent form, and scorer impact are multiplied by `played / 3`. This keeps one early blowout from dominating historical strength and neutral priors.

## Match Probabilities

Convert the team-rating delta through a logistic curve.

- Group-stage matches include a draw probability, highest when teams are close.
- Knockout matches force a winner probability because the bracket must advance one team.
- If `--market-signals-file` is supplied and a matching market exists, blend model probabilities with market probabilities. The output keeps model, market, and blended probabilities separate in JSON.

Market blend weight defaults to `0.35` and is capped at `0.65`. Quality adjustments reduce the effective weight when a market has low volume, low liquidity, or wide spread.

## Final Ranking Simulation

For final forecasts, run Monte Carlo simulations:

1. Keep completed group-stage results fixed.
2. Simulate remaining group-stage matches.
3. Rank each group by points, goal difference, goals scored, then rating.
4. Advance each group top two plus the best eight third-place teams.
5. Resolve Round of 32 placeholders by matching eligible third-place groups to bracket slots.
6. Simulate knockouts through the final and third-place match.

Use a fixed seed when reproducibility matters. Increase `--runs` for more stable probabilities.

Champion futures from a market signals file can calibrate the champion marginal table. Runner-up, third-place, fourth-place, and most-likely podium tables remain model-simulation outputs unless future market data explicitly supports those ranking types.

`--seed` fixes the Monte Carlo random sequence only. It does not freeze OpenFootball, Elo, FIFA, or market-source data. Preserve generated reports in `forecasts/daily/` when an exact daily snapshot matters.

## Confidence Interpretation

Use three buckets when explaining results:

- High confidence: model and market agree, and market data is recent, liquid, and low-spread.
- Medium confidence: model and market point in the same direction but probabilities differ meaningfully.
- Low confidence or disagreement: market and model point to different winners, or market quality is weak.

Do not describe outputs as betting recommendations.
