# MLB Free Agent Valuation: WAR Projections, Uncertainty Ranges and Contract Pricing

A Python tool that projects a player's WAR for the next several seasons, puts an honest uncertainty range around each projection, and estimates what a contract should be worth. It is tested against past seasons and past free-agent deals, and it has special handling for rookies/call-ups and players coming back from missed time.

> **Status:** a learning project built to understand how front offices think about player value. It is a simple, transparent model, not a replacement for ZiPS, Steamer or a team's internal systems. See [Limitations](#limitations).

## Results

Run `python war_model.py --validate` and paste your numbers here (they are also saved to `validation/validation_report.txt`).

| Test | Hitters | Pitchers |
|---|---:|---:|
| WAR projection error (RMSE, wins) | 1.71 | 1.53 |
| Naive baseline (last season's WAR) | 2.02 | 1.92 |
| Improvement over naive baseline | 16% lower RMSE | 20% lower RMSE |
| Mean absolute error (MAE, wins) | 1.33 | 1.16 |
| Average projection bias | +0.09 | +0.12 |
| Correlation between projected and actual WAR | 0.51 | 0.36 |

The WAR backtest covers 2021–2026 and includes 1,892 hitter observations and 1,665 pitcher observations.

## Quickstart

```bash
pip install -r requirements.txt
python war_model.py              # interactive calculator
```

The first run downloads Baseball-Reference WAR through [pybaseball](https://github.com/jldbc/pybaseball) and caches it in `data/`. It also creates `contracts.csv` (155 free-agent deals) if you don't have one.

In the calculator you type a player's name and answer two questions: the total contract and the number of years. After the results, one keystroke gets you a different contract, a position change, a saved chart, or a comparison with another player. Type `compare` (or `judge vs soto`) to put two players side by side. All the knobs (price of a win, range width, seasons, regression amounts) are in `settings.toml`.

| Command | What it does |
|---|---|
| `python war_model.py` | Interactive: type a player, a contract length, and optionally an offer. |
| `python war_model.py --validate` | Full validation: data checks, WAR backtest, contract out-of-time test. Saved to `validation/validation_report.txt`. |
| `python war_model.py --backtest` | WAR projection accuracy test only. |
| `python war_model.py --tune` | Tries other recency weights and regression amounts: picked on early seasons, confirmed on recent ones. |
| `python war_model.py --freeagents [file]` | Projects a list of free agents (default `free_agents.csv`) and saves `reports/free_agent_class_report.csv` and a formatted `.md` table. |
| `python war_model.py --check` | Checks your setup and data, and shows the inferred position groups. Run this first if anything looks off. |

Money can be typed any way you like: `150`, `$150M`, `150 million`, `$150,000,000`.

## How it works

**1. Projecting WAR.** Everything is done in rate terms (WAR per 600 PA for hitters, per 180 IP for pitchers), then multiplied by projected playing time.

1. *Aging curve:* for every pair of back-to-back seasons, measure how a player's rate changed from age a to a+1, and fit a smooth quadratic through those changes (weighted by playing time). Playing time gets its own curve. *Survivor-bias fix (off by default):* an experimental option counts players who vanish from the data as having dropped to replacement level, so the curve isn't built only from players who kept their jobs (`survivor_bias_weight` in the settings). In the backtest it did not improve accuracy (hitters tied; pitchers slightly worse), so it is off. `--backtest` still shows it as its own row.
2. *Age-adjust:* move each of the last three seasons to the player's current age.
3. *Weighted average:* weights 5/4/3 (most recent first), each multiplied by that season's PA or IP.
4. *Regress to the mean:* add 1,200 PA (hitters) or 500 IP (pitchers) of league-average performance, so small samples are pulled toward average.
5. *Playing time:* year one is `0.5 x last + 0.1 x the year before + 200 PA` for hitters (`+60 IP` for starters, `+25 IP` for relievers), then aged forward with the playing-time curve (never increasing after 30).
6. *WAR* = projected rate x projected playing time / 600 (or 180).

The approach is in the style of Tom Tango's Marcel projections. The weights and regression amounts are starting values, not tuned.

**Hitters: position-aware components.** Hitter WAR is built from parts, and the parts behave differently, so each is projected on its own and added back together (`hitter_model = "components"` in `settings.toml`; set `"total"` for the single-rate version, and `--backtest` compares the two):

- *Batting* (fairly stable), *baserunning* (less stable), *fielding* (very noisy, so regressed hardest, and fades faster at demanding positions) and the *positional adjustment* (a fixed credit for the position played: shortstop and catcher earn more than a corner outfielder, 1B or DH).
- Each part is regressed toward the average **for his position group** (shortstops are not compared with first basemen) and aged with its own curve. Fielding and position curves depend on position class (C/SS, 2B/3B/CF, corner), so a shortstop's defense and position credit fade differently from a right fielder's, including players who move down the defensive spectrum with age.
- Position is **inferred** from each player's positional adjustment (Baseball-Reference's WAR file has no position column), so it is approximate. `--check` lists the groups with example names so you can confirm they make sense. Override a player by pressing `p` after his results, or with a `pos` column in `free_agents.csv`.
- Pitchers still use WAR per inning pitched. A component model for pitchers needs strikeout, walk and FIP data, which Baseball-Reference's WAR file does not include.
- The parts come from Baseball-Reference's published WAR components (`runs_bat`, `runs_br`, `runs_dp`, `runs_field`, `runs_position`, `runs_catcher`) and add back to total WAR.

**2. Rookies, call-ups and players who missed time.** The base playing-time formula punishes both groups, so there is special handling (switch it off with `use_special_cases = false` in `settings.toml`). The backtest reports whether it helps.

- *Limited MLB history* (3-year total of 1,000 PA or less, or 260 IP or less): playing time is projected from the player's role, using PA per game x 145 games for hitters who play every day (3.4+ PA per game), IP per start x 28 for starters, or IP per appearance x 60 for relievers. The model never lowers the standard projection this way.
- *Missed time* (a recent season under 60% of his best of the two before, after a full season): playing time is set to 90% of his healthy seasons.
- *Your own number:* the calculator asks for expected PA or IP when a player has limited history or missed time, and `free_agents.csv` accepts an `expected_vol` column for any player.
- Both groups get wider uncertainty ranges, scaled from how much worse the model actually did on them in the backtest.

**3. Uncertainty ranges.** The projection is backtested 1, 2 and 3 seasons ahead for every season since 2019. How far off it was determines the range around each projection:

- The range covers `range_level` of past outcomes (default 68%; set 0.50, 0.80 or 0.90 in `settings.toml`). A wider level is not "more accurate", it just covers more of the possible outcomes.
- It depends on the projected-WAR tier (stars are harder to project), widens with the horizon (beyond year 3 it grows with the square root of time), is narrower for veterans with a full track record, and wider for rookies and players who missed time. Each multiplier is measured in the backtest, not guessed.
- The range for a whole contract is not the sum of the yearly ranges. The backtest measures how strongly one year's miss predicts the next (rho); a miss that fades is partly cancelled by other years, so the total is tighter than adding years up.
- `--validate` checks the ranges honestly: it builds them from earlier seasons and reports how often later outcomes landed inside.

The real way to tighten ranges is a more accurate model, not a narrower display. `--tune` and the roadmap items below are aimed at that.

**4. Pricing a contract.** Two methods, shown side by side:

- **(A) Market rate:** projected WAR x the price of a win, growing 5% a year. Negative WAR counts as $0. With `price_per_win = "auto"` (the default in `settings.toml`) the price is *measured*: for each past winter, total dollars paid divided by the wins the model projected for those deals, averaged over the last three winters and kept separately for hitters and pitchers. The `--validate` report shows it by winter. Because it is calibrated on the same deals, (A) says what the *typical* deal pays per projected win, so it is best for comparing players. Type a number in the settings to force a price.
- **(B) Regression:** ordinary least squares on real free-agent deals. The target is average annual value; the inputs are projected WAR for the first season (built using only data available when he signed), age, contract length, signing year, OPS+ (hitters) and a starter/reliever flag (pitchers). It reports an out-of-sample R^2 from leave-one-out cross-validation.

When you enter an offer, it is compared with both, with a break-even WAR and a verdict (bargain, fair, overpay). Every result also has a **price sensitivity** line: what the contract is worth if a win costs 25% less or more, and what price per projected win your offer implies. That matters because the price of a win is the least certain input, and the labor agreement expires this winter.

## Validation

`python war_model.py --validate` runs four things:

1. **Data checks:** player counts per season, duplicates, WAR outliers, partial-season warnings, and a check of every row in `contracts.csv`.
2. **WAR backtest:** for each season from 2019, the model is rebuilt using only earlier data, projects the next season, and is compared with what happened. It is scored against the naive guess (last season's WAR), a plain 3-year average, and itself with the aging curve or regression removed. It also breaks results out by age group, projection tier, and the rookie / missed-time groups.
3. **Range calibration:** ranges are built from earlier seasons and checked against later ones.
4. **Contract out-of-time test:** for each winter, the contract model is fit only on earlier winters' deals and asked to price that winter's deals, then compared with an implied $/WAR rule and with simply guessing the average salary.

Caveat: only players who played enough in the target season are scored, so the WAR backtest says nothing about players who lose their jobs or get hurt.

## Data

- **WAR:** Baseball-Reference (bWAR) via pybaseball (`SOURCE = "fangraphs"` is available but FanGraphs often blocks cloud IPs). 2020 is scaled to a 162-game pace.
- **Contracts:** `contracts.csv` holds 155 free-agent deals (winters after the 2019 to 2025 seasons) compiled from Spotrac, MLB.com, NBC Sports, ESPN, CBS Sports, Yahoo Sports and AP, using total guaranteed value. Deferred money is not discounted and opt-outs are treated as guaranteed. Ohtani (deferrals), players with no MLB history, extensions and qualifying-offer acceptances are excluded. Please verify against Spotrac or Cot's before relying on any single row.
- Raw downloaded data is **not** committed (see `.gitignore`). Check each site's terms of use before redistributing data.

## Limitations

- Baseball is noisy. Even good projection systems miss by around a win or more per player per season.
- No injury data: "missed time" is inferred from playing time, so it cannot tell injury from demotion or a platoon.
- Positions are inferred from the positional adjustment, so part-time or multi-position players can land in the wrong group. Pitchers have no component model. There are no park effects or batted-ball (Statcast) inputs beyond what WAR contains.
- Whether the component model beats the single-rate model is an empirical question: check the backtest.
- Aging curves are fit on active players, which overstates how well older players hold up (survivor bias). Playing time gains after 30 are capped to limit this.
- The contract regression is trained on about 150 deals: it is linear, ignores position and market context, and a few very large deals pull on it.
- The $/WAR price is an assumption, and a new labor agreement could change the market.
- Free-agent lists change: options, opt-outs and extensions decide who reaches the market.

## AI assistance

This project was developed with help from Claude (Anthropic) for code, debugging and documentation. I reviewed, ran and can explain the model. _(Edit this note to describe your own contribution.)_

## Roadmap

- Statcast inputs for hitters (exit velocity, barrel rate, sprint speed) and pitch-level inputs for pitchers
- Pitcher components (K-BB%, FIP) where FanGraphs or Savant data is reachable
- Park effects, and a better position classifier (for example from fielding innings)
- Adopt tuned weights and regression amounts from `--tune` if they hold up on the confirmation seasons
- Separate playing-time risk (injuries) from performance risk in the ranges
- A web or notebook front end
- Compare against a public system (Steamer / ZiPS)
- Log-scale salary model and year-adjusted dollars

## Repository layout

```
war_model.py            start here (a thin launcher)
settings.toml           every setting you might change, with comments
mlbwar/                 the code, split by job
  config.py             defaults, settings loader, fixed tables
  data.py  util.py      loading/cleaning WAR data; name, money and position helpers
  aging.py              aging curves and fitted models
  projection.py         projecting a player (components, rookies, missed time)
  pricing.py            price of a win, market-rate value, price sensitivity
  ranges.py             uncertainty ranges from the backtest
  contracts.py          contract file and regression model
  display.py  charts.py printing results, comparing players, charts
  validation.py         backtest, tuning, data checks, validation report
  reports.py            free-agent class report (csv, markdown, chart)
  cli.py                the interactive program and command-line options
contracts.csv           free-agent deals used by the contract model
free_agents.csv         the class to project (starter list: confirm before use)
tests/                  unit tests (pytest)
requirements.txt
validation/             validation_report.txt and backtest files from --validate (commit the report)
reports/                free-agent class tables and chart from --freeagents, and your written analysis
charts/                 charts saved from the calculator
```

## License

MIT (see `LICENSE`).
