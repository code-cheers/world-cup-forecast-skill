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

Current-tournament signals are sample-weighted. Before a team has completed all three group matches, points per match, goal difference, goals scored, recent form, and scorer impact are multiplied by `played / 3`. This keeps one early blowout from dominating historical strength and neutral priors.

## Match Probabilities

Convert the team-rating delta through a logistic curve.

- Group-stage matches include a draw probability, highest when teams are close.
- Knockout matches force a winner probability because the bracket must advance one team.

## Final Ranking Simulation

For final forecasts, run Monte Carlo simulations:

1. Keep completed group-stage results fixed.
2. Simulate remaining group-stage matches.
3. Rank each group by points, goal difference, goals scored, then rating.
4. Advance each group top two plus the best eight third-place teams.
5. Resolve Round of 32 placeholders by matching eligible third-place groups to bracket slots.
6. Simulate knockouts through the final and third-place match.

Use a fixed seed when reproducibility matters. Increase `--runs` for more stable probabilities.
