# MLB Free Agent Valuation: WAR Projections, Uncertainty Ranges, and Contract Pricing

A Python baseball analytics project that projects future player performance, quantifies uncertainty, and estimates MLB free-agent contract value.

> **Status:** Learning and portfolio project with historical backtesting. The model shows improvement over several simple baselines, but it remains a transparent experimental model rather than a replacement for established projection systems or proprietary MLB team models.

---

# Overview

How much value is an MLB player likely to provide over the next several seasons—and what might that production be worth in free agency?

This project explores those questions through a transparent Python model that combines:

- Historical **Wins Above Replacement (WAR)**
- Player aging curves
- Weighted historical performance
- Regression toward league-average performance
- Playing-time projections
- Uncertainty ranges
- Historical MLB free-agent contract data
- Out-of-time validation

The tool projects a player's future WAR, produces uncertainty ranges around those projections, and estimates potential contract value using two different approaches:

1. **A market-rate WAR valuation**, based on projected WAR and an assumed dollar value per win.
2. **A regression-based contract model**, trained on historical free-agent contracts.

The project also includes optional special handling for:

- Players with limited MLB experience
- Rookies and call-ups
- Players returning from substantially reduced playing time

This project is intended to explore how quantitative analysis can support **player evaluation, baseball operations, and contract research**.

It is a learning project and is **not** intended to replace established public projection systems such as ZiPS or Steamer, nor proprietary systems used by MLB organizations.

---

# Key Results

## WAR Projection Accuracy

The model was evaluated against historical player seasons from **2021 through 2026**.

For each historical forecast, the model was rebuilt using information available before the season being predicted and compared with what actually happened. The model was also compared with simpler prediction methods.

| Metric | Hitters | Pitchers |
|---|---:|---:|
| **Player-seasons evaluated** | 1,892 | 1,665 |
| **Full model RMSE** | **1.71 WAR** | **1.53 WAR** |
| **Previous-season WAR baseline RMSE** | 2.02 WAR | 1.92 WAR |
| **Three-year weighted-average RMSE** | 1.82 WAR | 1.67 WAR |
| **Improvement over previous-season baseline** | **16% lower RMSE** | **20% lower RMSE** |
| **Mean bias (actual − predicted)** | +0.09 WAR | +0.12 WAR |
| **Prediction-to-outcome correlation** | 0.51 | 0.36 |

### What does this mean?

The most important measure in this table is **RMSE**, or Root Mean Squared Error.

In simple terms, RMSE measures how far projections tend to be from actual outcomes, while giving larger mistakes extra weight.

For example:

- The hitter model had an RMSE of **1.71 WAR**.
- The pitcher model had an RMSE of **1.53 WAR**.

This does **not** mean every hitter was exactly 1.71 WAR above or below his projection. Some projections were much closer, while some were much farther away. RMSE summarizes the overall size of the model's errors and penalizes especially large misses.

The model performed better than simply predicting that a player would repeat his previous season's WAR:

- **Hitters:** RMSE decreased from 2.02 to 1.71.
- **Pitchers:** RMSE decreased from 1.92 to 1.53.

That represents approximately a **16% reduction in RMSE for hitters** and a **20% reduction for pitchers** compared with the previous-season baseline.

A positive mean bias means that, on average, actual performance was slightly higher than projected. The overall biases were relatively small:

- Hitters: **+0.09 WAR**
- Pitchers: **+0.12 WAR**

The model therefore showed a small tendency to project players slightly lower than their eventual actual WAR.

---

# Comparing the Model With Simpler Approaches

The validation process also tested whether individual components of the model appeared to contribute to accuracy.

## Hitters

| Method | RMSE | MAE | Bias | Correlation |
|---|---:|---:|---:|---:|
| **Full model** | **1.71** | **1.33** | **+0.09** | **0.51** |
| Total-WAR-rate model (no components) | 1.71 | 1.33 | +0.10 | 0.51 |
| Without aging curve | 1.77 | 1.40 | -0.32 | 0.49 |
| Without regression to the mean | 1.71 | 1.33 | +0.09 | 0.51 |
| Plain 3-year weighted average | 1.82 | 1.43 | -0.09 | 0.50 |
| Naive: previous season's WAR | 2.02 | 1.58 | -0.10 | 0.48 |

## Pitchers

| Method | RMSE | MAE | Bias | Correlation |
|---|---:|---:|---:|---:|
| **Full model** | **1.53** | **1.16** | **+0.12** | **0.36** |
| Without aging curve | 1.55 | 1.19 | -0.15 | 0.36 |
| Without regression to the mean | 1.82 | 1.39 | +0.23 | 0.32 |
| Plain 3-year weighted average | 1.67 | 1.29 | +0.10 | 0.34 |
| Naive: previous season's WAR | 1.92 | 1.48 | +0.05 | 0.30 |

### What did this comparison show?

### Aging curves

Removing the aging curve made the model worse for both groups:

- Hitters: RMSE increased from **1.71 to 1.77**
- Pitchers: RMSE increased from **1.53 to 1.55**

The improvement is modest, but the backtest suggests that explicitly accounting for aging adds some predictive value.

### Regression to the mean

Regression to the mean produced different results for hitters and pitchers.

For pitchers, it appeared to be important:

- Full model: **1.53 RMSE**
- Without regression to the mean: **1.82 RMSE**

For hitters, the current backtest produced essentially the same overall RMSE with and without this component:

- Full model: **1.71 RMSE**
- Without regression to the mean: **1.71 RMSE**

Therefore, this project does **not** claim that the current regression-to-the-mean implementation improves hitter RMSE based on this validation result. That is an area for further investigation and tuning.

This distinction is important: a model component may sound statistically reasonable, but it should not be considered successful unless testing demonstrates measurable improvement.

---

# Accuracy by Player Age

The model was also compared with the previous-season baseline across different age groups.

## Hitters

| Age Group | Players | Model RMSE | Naive RMSE |
|---|---:|---:|---:|
| 26 and under | 581 | 1.92 | 2.13 |
| 27–30 | 768 | 1.59 | 1.92 |
| 31–34 | 441 | 1.65 | 2.07 |
| 35+ | 102 | 1.47 | 1.92 |

## Pitchers

| Age Group | Players | Model RMSE | Naive RMSE |
|---|---:|---:|---:|
| 26 and under | 391 | 1.77 | 2.07 |
| 27–30 | 686 | 1.46 | 1.86 |
| 31–34 | 426 | 1.43 | 1.90 |
| 35+ | 162 | 1.40 | 1.86 |

The model outperformed the previous-season baseline across every reported age group.

This does not mean that every individual player is easy to project. Instead, it means that across these historical groups, the model produced smaller overall prediction errors than simply carrying forward the player's previous WAR.

---

# Accuracy by Projected Performance Tier

Higher-performing players can be especially difficult to project because extreme performance is less common and because individual outcomes can vary substantially.

## Hitters

| Projected WAR Tier | Players | Model RMSE | Naive RMSE |
|---|---:|---:|---:|
| Below 1 WAR | 645 | 1.47 | 1.72 |
| 1 to 2.5 WAR | 785 | 1.63 | 1.90 |
| 2.5 to 4 WAR | 350 | 1.98 | 2.36 |
| 4+ WAR | 112 | 2.40 | 3.03 |

## Pitchers

| Projected WAR Tier | Players | Model RMSE | Naive RMSE |
|---|---:|---:|---:|
| Below 1 WAR | 900 | 1.25 | 1.62 |
| 1 to 2.5 WAR | 598 | 1.69 | 2.03 |
| 2.5 to 4 WAR | 141 | 2.15 | 2.72 |
| 4+ WAR | 26 | 2.21 | 3.34 |

The model continued to outperform the naive previous-season baseline across all reported projected-WAR tiers.

However, the results also show that **higher-WAR players are generally harder to project accurately**. This is one reason the project uses uncertainty ranges rather than presenting every projection as a precise prediction.

---

# Rookies, Call-Ups, and Players Returning From Missed Time

The project includes optional special handling for players whose recent MLB playing time may not represent their expected future opportunity.

These rules were specifically tested rather than simply assumed to improve the model.

## Hitters

### Limited MLB History

- With special handling: **RMSE 1.66**
- Without special handling: **RMSE 1.58**

The special handling did not improve overall RMSE for this group, although it reduced the average bias from **+0.32 to +0.05 WAR**.

### Players Returning From Missed Time

- With special handling: **RMSE 1.52**
- Without special handling: **RMSE 1.48**

Again, the special handling did not improve overall RMSE in this test, but it changed the bias substantially.

## Pitchers

### Limited MLB History

- With special handling: **RMSE 1.35**
- Without special handling: **RMSE 1.34**

### Players Returning From Missed Time

- With special handling: **RMSE 1.80**
- Without special handling: **RMSE 1.78**

For pitchers, the current special-handling rules also did not improve overall RMSE.

### Conclusion

The current validation does **not** support claiming that the special rookie/call-up or missed-time rules improve overall RMSE.

However, some of these rules affected bias, which suggests that they may change *how* errors are distributed even when they do not reduce total error.

The next step is to investigate whether these rules should be:

- Retuned,
- Applied only to specific player groups,
- Used primarily for uncertainty rather than point projections, or
- Removed if additional validation continues to show no predictive benefit.

This is an important example of why backtesting matters: a feature should not remain in a model simply because it appears theoretically reasonable.

---

# How the WAR Projection Model Works

The model projects performance in **rate terms** and then multiplies the projected rate by expected playing time.

- Hitters: WAR per **600 plate appearances**
- Pitchers: WAR per **180 innings pitched**

This helps separate two related but different questions:

1. **How effective is the player likely to be when playing?**
2. **How much is the player likely to play?**

## Step 1: Aging Curves

The model examines historical changes in player performance between consecutive ages.

For each pair of back-to-back seasons, it measures how a player's performance rate changed from one age to the next and fits a smooth quadratic aging curve. Playing time has its own aging curve.

Examples of the estimated expected changes include:

### Hitters, per 600 PA

- Age 24 → 25: **−0.10 WAR**
- Age 27 → 28: **−0.34 WAR**
- Age 30 → 31: **−0.55 WAR**
- Age 33 → 34: **−0.71 WAR**
- Age 36 → 37: **−0.84 WAR**

### Pitchers, per 180 IP

- Age 24 → 25: **−0.07 WAR**
- Age 27 → 28: **−0.19 WAR**
- Age 30 → 31: **−0.36 WAR**
- Age 33 → 34: **−0.57 WAR**
- Age 36 → 37: **−0.84 WAR**

These curves represent average historical patterns, not guarantees for any individual player.

---

## Step 2: Age-Adjust Recent Seasons

The model adjusts each player's recent seasons to a common age before combining them.

This helps prevent a player's performance from being treated as identical regardless of whether it occurred at age 24 or age 34.

---

## Step 3: Weighted Historical Performance

The model uses the player's three most recent seasons with recency weights:

**5 / 4 / 3**

The most recent season receives the largest weight.

Those weights are also multiplied by playing time, meaning that a full season generally provides more information than a very small sample.

---

## Step 4: Regression to the Mean

The model pulls small or extreme samples toward league-average performance.

The current implementation adds the equivalent of:

- **1,200 PA** of league-average performance for hitters
- **500 IP** of league-average performance for pitchers

The purpose is to prevent small samples from producing extremely confident projections.

However, validation matters more than theory. In the current backtest, removing this component substantially worsened pitcher accuracy but did not change the overall hitter RMSE.

Future versions may retune these values separately.

---

## Step 5: Project Playing Time

The model estimates future opportunity separately from performance.

For the first projected year:

### Hitters

```text
0.5 × last season's PA
+ 0.1 × the previous season's PA
+ 200 PA
```

### Starting Pitchers

```text
0.5 × last season's IP
+ 0.1 × the previous season's IP
+ 60 IP
```

### Relief Pitchers

```text
0.5 × last season's IP
+ 0.1 × the previous season's IP
+ 25 IP
```

Playing time is then adjusted using the playing-time aging curve.

Under the current model, projected playing time is not increased after age 30 through the aging adjustment.

---

## Step 6: Calculate Projected WAR

Finally:

```text
Projected WAR =
Projected performance rate × Projected playing time
```

Scaled appropriately:

- Divide by **600 PA** for hitters
- Divide by **180 IP** for pitchers

The general approach is inspired by the philosophy of **Marcel-style projections**, emphasizing transparency, historical performance, recency weighting, and regression toward average performance.

---

# Biggest Projection Misses

No baseball projection system perfectly predicts individual seasons.

Some of the largest historical misses included major breakouts, unexpected elite performances, and major declines.

### Examples among hitters

- Jarren Duran, 2024: projected **1.3 WAR**, actual **9.0 WAR**
- Bobby Witt Jr., 2024: projected **2.8 WAR**, actual **9.6 WAR**
- Austin Riley, 2021: projected **−0.1 WAR**, actual **6.3 WAR**
- Aaron Judge, 2022: projected **4.5 WAR**, actual **10.8 WAR**
- Cody Bellinger, 2021: projected **4.3 WAR**, actual **−1.6 WAR**

### Examples among pitchers

- Robbie Ray, 2021: projected **0.5 WAR**, actual **6.9 WAR**
- Cristopher Sánchez, 2025: projected **2.5 WAR**, actual **8.1 WAR**
- Alek Manoah, 2023: projected **4.1 WAR**, actual **−1.1 WAR**
- Tarik Skubal, 2024: projected **1.6 WAR**, actual **6.7 WAR**

These examples illustrate an important limitation of forecasting: models can perform reasonably well across thousands of observations while still missing dramatically on individual players.

---

# Uncertainty Ranges

A projection should not be interpreted as a precise prediction.

For example, if a player is projected for **3 WAR**, the realistic outcome could be substantially higher or lower.

This project therefore builds uncertainty ranges from historical projection errors.

The ranges vary based on factors including:

- Projected WAR tier
- Forecast horizon
- Player experience
- Limited MLB history
- Recent missed playing time

The default range level is **68%**, although other levels can be configured.

A 68% range is intended to contain approximately 68% of comparable future outcomes.

---

## Range Calibration Results

The model tests its ranges on later seasons rather than evaluating them only on the same data used to construct them.

### Hitters

Of **952 later player-seasons**:

> **68% landed inside the nominal 68% range**

This is very close to perfect calibration for the target level.

### Pitchers

Of **832 later player-seasons**:

> **72% landed inside the nominal 68% range**

The pitcher ranges covered slightly more outcomes than expected, suggesting they may currently be somewhat conservative or wider than necessary.

### What is rho?

For multi-year contracts, the project estimates the relationship between forecast errors in consecutive seasons.

The estimated correlation values were:

- **Hitters: rho = 0.43**
- **Pitchers: rho = 0.33**

A rho of 1.00 would mean that errors were perfectly correlated from year to year.

Because the observed correlations are lower than 1.00, the model does not simply add every annual uncertainty range together when estimating uncertainty across an entire contract.

---

# Contract Valuation

The project uses two different approaches to estimate contract value.

## Method A: Market-Rate WAR Valuation

The first method multiplies projected WAR by an assumed dollar value per WAR.

Conceptually:

```text
Projected WAR × Dollars per WAR
```

The assumed market price per WAR grows by **5% annually** in the current model.

Negative WAR is valued at $0 in this calculation.

This method is intentionally simple and should be viewed as a benchmark rather than a precise prediction of what a specific MLB team will pay.

---

## Method B: Regression-Based Contract Valuation

The second method uses ordinary least squares regression trained on historical MLB free-agent contracts.

The target is:

> **Average Annual Value (AAV)**

The model includes variables such as:

- First-year projected WAR
- Player age
- Contract length
- Signing year
- OPS+ for hitters
- Starter/reliever status for pitchers

The regression attempts to identify relationships between these characteristics and historical contract values.

This does **not** mean the model can perfectly predict negotiations or determine what a specific team will offer.

Instead, it provides a statistically tested estimate based on patterns in historical contracts.

---

# Contract Model Validation

The contract model was tested using an **out-of-time validation approach**.

For each offseason:

1. The model was trained only on earlier free-agent contracts.
2. It was then used to predict contracts from a later offseason.
3. Predictions were compared with the actual contracts.

This is more meaningful than evaluating the model only on the same contracts used to train it.

## Hitters

**54 contracts tested across the 2022–2025 winters.**

| Method | RMSE ($M/year) | MAE ($M/year) | Rank Correlation |
|---|---:|---:|---:|
| **Regression model** | **$7.93M** | **$5.32M** | **0.81** |
| Implied $/WAR rule | $8.46M | $5.59M | 0.80 |
| Average earlier AAV baseline | $11.96M | $9.16M | 0.12 |

The regression model had the lowest overall RMSE.

Compared with the simple implied $/WAR rule, the regression reduced RMSE from **$8.46 million per year to $7.93 million per year**.

## Pitchers

**55 contracts tested across the 2023–2025 winters.**

| Method | RMSE ($M/year) | MAE ($M/year) | Rank Correlation |
|---|---:|---:|---:|
| **Regression model** | **$5.46M** | **$4.33M** | **0.53** |
| Implied $/WAR rule | $7.48M | $6.04M | 0.56 |
| Average earlier AAV baseline | $8.00M | $6.99M | 0.25 |

For pitchers, the regression model showed a larger improvement over the simple $/WAR rule.

RMSE decreased from:

> **$7.48 million per year → $5.46 million per year**

---

# How to Interpret Contract RMSE

A contract RMSE of **$7.93 million per year** for hitters does **not** mean that every contract prediction was exactly $7.93 million too high or too low.

Instead, it summarizes the overall size of prediction errors across all tested contracts, while giving larger mistakes more weight.

For example:

- Some contracts may have been predicted within a few million dollars per year.
- Others may have been off by much more.
- Very large misses affect RMSE more heavily.

The hitter model's average absolute error (MAE) was **$5.32 million per year**, which is another useful measure of typical prediction error that does not penalize extremely large misses as heavily as RMSE.

---

# Contract Model Biggest Misses

The largest contract errors demonstrate why contract valuation is difficult.

Examples include:

### Hitters

- Kyle Tucker: actual **$60.0M AAV**, model estimate **$25.9M**
- Bo Bichette: actual **$42.0M AAV**, model estimate **$20.2M**
- Alex Bregman: actual **$35.0M AAV**, model estimate **$20.6M**

### Pitchers

- Tyler Mahle: actual **$10.0M AAV**, model estimate **$24.3M**
- Jose Quintana: actual **$6.0M AAV**, model estimate **$19.0M**
- Framber Valdez: actual **$38.3M AAV**, model estimate **$27.5M**

These misses reinforce an important limitation: MLB contracts are influenced by more than projected WAR.

Factors not fully captured by this model can include:

- Team-specific demand
- Position scarcity
- Market timing
- Medical information
- Player reputation
- Defensive value
- Competition among teams
- Contract structure
- Risk preferences

---

# Current Contract Dataset

The contract model currently uses:

- **155 rows**
- **154 usable contracts**
- Free-agent winters from **2019 through 2025**
- **77 hitter contracts**
- **77 pitcher contracts**

One player, **Matt Boyd**, was skipped because the player name could not be matched reliably in the WAR data.

The dataset also contains very large contracts, including:

- Juan Soto: **$51M AAV**
- Kyle Tucker: **$60M AAV**

Large contracts can have substantial influence on a linear regression, which is an important limitation and an area for future investigation.

---

# Data

## WAR Data

WAR data comes from **Baseball-Reference through pybaseball**.

The project uses Baseball-Reference WAR (bWAR).

The shortened 2020 season is scaled to a 162-game pace for the model's historical framework.

A FanGraphs source option exists, although FanGraphs data access may be limited in some environments.

## Contract Data

`contracts.csv` contains historical free-agent contracts compiled from sources including:

- Spotrac
- MLB.com
- NBC Sports
- ESPN
- CBS Sports
- Yahoo Sports
- Associated Press

The dataset uses total guaranteed contract value.

Current assumptions include:

- Deferred money is not discounted.
- Opt-outs are treated as guaranteed.
- Shohei Ohtani's deferred contract is excluded.
- Players without MLB history are excluded.
- Extensions are excluded.
- Qualifying-offer acceptances are excluded.

Individual contract entries should be independently verified before being relied upon for research or financial decisions.

Raw downloaded data is not committed to the repository.

---

# Validation Process

Run the complete validation suite with:

```bash
python war_model.py --validate
```

The validation process includes four major sections.

## 1. Data Checks

The program checks:

- Player counts by season
- Duplicate records
- WAR outliers
- Partial-season issues
- Contract dataset rows

Current validation covers:

- **6,257 hitter player-seasons**
- **1,533 hitters**
- **6,538 pitcher player-seasons**
- **1,852 pitchers**

The dataset covers seasons from **2015 through 2026**.

---

## 2. WAR Projection Backtest

The model is rebuilt using historical information available before each prediction.

It is then compared against:

- Actual future WAR
- Previous-season WAR
- A three-year weighted average
- Model variants without the aging curve
- Model variants without regression to the mean

Results are also broken down by:

- Player age
- Projected performance tier
- Limited MLB history
- Recent missed time

---

## 3. Range Calibration

Historical projection errors are used to construct uncertainty ranges.

Those ranges are then tested on later outcomes.

The key question is:

> **Does a stated 68% range actually contain approximately 68% of future outcomes?**

The current results were:

- **Hitters: 68% inside a 68% range**
- **Pitchers: 72% inside a 68% range**

This provides evidence that the hitter ranges are closely calibrated at the tested level, while the pitcher ranges may be somewhat conservative.

---

## 4. Contract Out-of-Time Test

The contract model is trained on earlier contracts and tested on later free-agent winters.

It is compared with:

- The regression model
- A simple implied dollars-per-WAR rule
- Predicting the average salary from earlier deals

This helps test whether the additional complexity of the regression produces measurable improvement over simpler methods.

---

# Important Caveat About the WAR Backtest

The WAR backtest currently scores only players who played enough in the target season.

Therefore, the reported results do **not fully measure** the model's ability to predict:

- Serious injuries
- Players losing their jobs
- Demotions
- Major reductions in playing time

This is a significant limitation because playing-time risk is a major part of baseball forecasting.

Future versions should attempt to separate:

1. **Performance uncertainty** — how good a player will be when playing.
2. **Playing-time uncertainty** — how much the player will actually play.

---

# Quick Start

Install the required packages:

```bash
pip install -r requirements.txt
```

Run the interactive calculator:

```bash
python war_model.py
```

---

# Commands

| Command | What it does |
|---|---|
| `python war_model.py` | Interactive calculator: enter a player, contract length, and optionally an offer |
| `python war_model.py --validate` | Runs data checks, WAR backtesting, range calibration, and contract validation |
| `python war_model.py --backtest` | Runs the WAR projection backtest |
| `python war_model.py --tune` | Tests alternative recency weights and regression amounts |
| `python war_model.py --freeagents [file]` | Projects a free-agent list and saves a report |

The first run downloads and caches WAR data in the `data/` directory.

The project can also create:

- `validation_report.txt`
- `validation/backtest_bat.csv`
- `validation/backtest_pit.csv`
- `free_agent_class_report.csv`

---

# Money Input

Contract values can be entered in several formats, including:

```text
150
$150M
150 million
$150,000,000
```

---

# Limitations

This project has several important limitations.

- Baseball performance is inherently noisy, and individual player seasons are difficult to predict.
- The model does not directly incorporate injury information.
- Reduced playing time cannot always distinguish injury from demotion, platoon usage, or other factors.
- The model does not explicitly include position-specific effects.
- Detailed defensive metrics are not separately modeled.
- Park effects are not separately modeled.
- Statcast and detailed batted-ball or pitch-level data are not currently included beyond information already reflected in WAR.
- Aging curves are estimated from active players, creating potential survivor bias.
- Playing-time gains after age 30 are capped to help limit some effects of this issue.
- The contract regression is trained on a relatively small dataset of approximately 150 deals.
- The regression is linear and does not capture all market conditions.
- Very large contracts can influence regression results.
- The dollars-per-WAR assumption is a benchmark rather than a guaranteed market price.
- MLB's labor environment and future collective bargaining agreements could change contract markets.
- Free-agent classes can change through options, opt-outs, extensions, and other transactions.

Most importantly:

> **A model producing a numerical answer does not automatically mean the answer is correct.**

For that reason, this project emphasizes historical backtesting and comparison with simpler baselines.

---

# What I Learned From the Current Validation

The current validation produced several important lessons.

### What appears to work

- The full WAR projection model outperformed the previous-season WAR baseline for both hitters and pitchers.
- The model outperformed a simple three-year weighted average.
- Aging adjustments provided modest improvements.
- Regression to the mean substantially improved pitcher projections.
- The contract regression outperformed the simple implied $/WAR benchmark overall.
- The uncertainty ranges showed reasonable calibration, especially for hitters.

### What did not clearly improve the model

- The current regression-to-the-mean implementation did not improve overall hitter RMSE in the latest backtest.
- The current rookie/call-up and missed-time special-handling rules did not reduce overall RMSE.

These findings are important because they prevent the project from becoming a collection of features that merely *sound* sophisticated.

Each component should ultimately be judged by whether it improves prediction, calibration, interpretability, or another clearly defined objective.

---

# Roadmap

Planned improvements include:

- Add Statcast and pitch-level inputs
- Add position and park adjustments
- Tune recency weights and regression parameters using separate training and confirmation periods
- Investigate or redesign the rookie and missed-time rules
- Separate playing-time risk from performance risk
- Compare the model with public projection systems such as Steamer or ZiPS
- Experiment with log-scale salary modeling
- Adjust contract values for changes in the market over time
- Add additional contract and market variables
- Split the project into separate modules for data, projections, contracts, validation, and the command-line interface

---

# Repository Layout

```text
war_model.py              Main model and command-line interface
contracts.csv             Historical free-agent contracts
free_agents.csv           Free-agent list to project
requirements.txt          Required Python packages
validation_report.txt     Output from the full validation process

data/                     Cached baseball data
validation/               Backtest outputs
tests/                    pytest unit tests
reports/                  Written analyses and player reports
```

---

# AI Assistance

This project was developed with assistance from AI tools, including Claude, for coding, debugging, and documentation.

AI assistance was used to help implement and refine parts of the project, but the project is intended as a learning exercise. I reviewed the methodology, ran the validation, examined the outputs, and continue to improve my understanding of the programming and statistical decisions involved.

My goal is not simply to produce code that runs. The goal is to understand:

- How the model works
- What assumptions it makes
- How to test those assumptions
- Where the model performs well
- Where it fails
- How future versions can be improved

---

# License

This project is released under the **MIT License**. See `LICENSE` for details.
