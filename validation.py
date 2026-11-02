"""Backtest, tuning, data checks and the validation report."""

import os
import sys
import numpy as np
import pandas as pd

from .config import KIND, S, VALIDATION_DIR
from .aging import fit_models
from .projection import project
from .ranges import compute_error_bands, range_coverage
from .contracts import build_contract_table, contract_features, fit_ols, load_contracts


def backtest(data):
    """
    How accurate are the WAR projections? For every season t (2019 onward) the model is rebuilt
    using ONLY data through t, projects season t+1, and is compared with what really happened.
    It is also compared with simpler guesses and with versions of itself missing one ingredient.
    """
    for kind, cfg in KIND.items():
        df = data[kind]
        vol = cfg["vol"]
        rows = []
        for t in range(S.START_SEASON + 4, S.END_SEASON):
            if t + 1 == 2020:                       # skip the 60-game season as a target
                continue
            models = fit_models(df, kind, t)
            models_fix = fit_models(df, kind, t, dropout_weight=0.5)
            flat = {"rate": lambda a: 0.0, "vol": lambda a: 1.0, "prior": models["prior"]}
            hist = {i: g for i, g in df[df["Season"] <= t].groupby("IDfg")}
            target = df[(df["Season"] == t + 1) & (df[vol] >= cfg["bt_min"])]
            for _, tr in target.iterrows():
                g = hist.get(tr["IDfg"])
                if g is None or (g["Season"] == t).sum() == 0:
                    continue
                last3 = g[g["Season"] > t - 3]
                w = last3["Season"].map(lambda x: S.SEASON_WEIGHTS[int(t - x)])
                full = project(g, kind, models, t, 1)
                rows.append({
                    "Name": tr["Name"], "Season": t + 1, "Age": tr["Age"], "actual": tr["WAR"],
                    "model": full["war"][0], "limited": full["limited"], "injured": full["injured"],
                    "plain": project(g, kind, models, t, 1, special=False)["war"][0],
                    "dropfix": project(g, kind, models_fix, t, 1)["war"][0],
                    "total_rate": (project(g, kind, models, t, 1, method="total")["war"][0]
                                   if full["method"] == "components" else np.nan),
                    "no_aging": project(g, kind, flat, t, 1)["war"][0],
                    "no_regression": project(g, kind, models, t, 1, reg=0)["war"][0],
                    "last_season": g.loc[g["Season"] == t, "WAR"].iloc[0],
                    "avg_3yr": float((last3["WAR"] * w).sum() / w.sum()),
                })
        if not rows:
            continue
        res = pd.DataFrame(rows)
        label = cfg["label"] + "s"
        print(f"\n{'=' * 70}\nWAR PROJECTION BACKTEST: {label} ({len(res)} player-seasons, "
              f"{res['Season'].min()}-{res['Season'].max()})\n{'=' * 70}")

        methods = [("model", "Full model"), ("dropfix", "  with survivor-bias fix (experimental, weight 0.5)"), ("no_aging", "  without aging curve"),
                   ("no_regression", "  without regression to mean"),
                   ("avg_3yr", "Plain 3-yr weighted avg WAR"), ("last_season", "Naive: last season's WAR")]
        if res["total_rate"].notna().any():
            methods.insert(1, ("total_rate", "  total-WAR-rate model (no components)"))
        table = []
        for col, name in methods:
            err = res["actual"] - res[col]
            table.append({"Method": name, "RMSE": np.sqrt((err ** 2).mean()), "MAE": err.abs().mean(),
                          "Bias": err.mean(), "Corr": res["actual"].corr(res[col])})
        print(pd.DataFrame(table).round(2).to_string(index=False))
        m_rmse, n_rmse = table[0]["RMSE"], table[-1]["RMSE"]
        print(f"\nThe model's RMSE is {abs(1 - m_rmse / n_rmse) * 100:.0f}% "
              f"{'lower' if m_rmse < n_rmse else 'HIGHER'} than just using last season's WAR.")
        print("(RMSE/MAE = typical miss in WAR; Bias = actual minus projected, so positive means the model "
              "projects too low; Corr = how well the ranking of players matches.)")

        print("\nRookies / call-ups and players who missed time (does the special handling help?):")
        for flag, title in (("limited", "Limited MLB history"), ("injured", "Missed time the year before")):
            x = res[res[flag]]
            if len(x) < 5:
                print(f"  {title}: only {len(x)} cases, too few to judge")
                continue
            e1, e0 = x["actual"] - x["model"], x["actual"] - x["plain"]
            print(f"  {title}: N={len(x)} | with special handling: RMSE {np.sqrt((e1 ** 2).mean()):.2f}, "
                  f"bias {e1.mean():+.2f} | without: RMSE {np.sqrt((e0 ** 2).mean()):.2f}, bias {e0.mean():+.2f}")

        res["age_group"] = pd.cut(res["Age"], [0, 26, 30, 34, 60], labels=["26 and under", "27-30", "31-34", "35+"])
        res["tier"] = pd.cut(res["model"], [-20, 1, 2.5, 4, 30], labels=["proj < 1", "1 to 2.5", "2.5 to 4", "4+"])
        for col, title in (("age_group", "By age in the season being predicted"), ("tier", "By projected WAR")):
            rows_g = []
            for key, g in res.groupby(col, observed=True):
                rows_g.append({"group": key, "N": len(g),
                               "Model RMSE": np.sqrt(((g["actual"] - g["model"]) ** 2).mean()),
                               "Naive RMSE": np.sqrt(((g["actual"] - g["last_season"]) ** 2).mean()),
                               "Model bias": (g["actual"] - g["model"]).mean()})
            out = pd.DataFrame(rows_g).set_index("group")
            out["N"] = out["N"].astype(int)
            print(f"\n{title}:")
            print(out.round(2).to_string())

        res["miss"] = res["actual"] - res["model"]
        worst = res.reindex(res["miss"].abs().sort_values(ascending=False).index).head(8)
        print("\nBiggest misses:")
        print(worst[["Name", "Season", "Age", "model", "actual", "miss"]].round(1).to_string(index=False))

        os.makedirs(VALIDATION_DIR, exist_ok=True)
        path = os.path.join(VALIDATION_DIR, f"backtest_{kind}.csv")
        res.drop(columns=["age_group", "tier"]).round(3).to_csv(path, index=False)
        print(f"\nEvery projection vs. outcome was saved to {path}")
    print("\nNote: only players who actually played enough in the target season are scored, so the test "
          "says nothing about players who lose their jobs or get hurt.")

def tune(data):
    """
    Try different recency weights and regression amounts. Settings are PICKED using early seasons and then
    CONFIRMED on the most recent ones, so a lucky setting can't fool you. Smaller errors also mean tighter ranges.
    """
    original = list(S.SEASON_WEIGHTS)
    weight_options = [[5, 4, 3], [4, 3, 2], [3, 2, 1], [1, 1, 1], [6, 3, 1]]
    reg_options = {"bat": [600, 900, 1200, 1800, 2400], "pit": [250, 500, 750, 1000]}
    split_season = S.END_SEASON - 2
    print(f"\n{'=' * 70}\nTUNING: recency weights and regression amounts\n{'=' * 70}")
    print(f"Picked on target seasons before {split_season}, confirmed on {split_season} onward.")
    try:
        for kind, cfg in KIND.items():
            df, vol = data[kind], cfg["vol"]
            cases = []
            for t in range(S.START_SEASON + 4, S.END_SEASON):
                if t + 1 == 2020:
                    continue
                models = fit_models(df, kind, t)
                hist = {i: g for i, g in df[df["Season"] <= t].groupby("IDfg")}
                for tr in df[(df["Season"] == t + 1) & (df[vol] >= cfg["bt_min"])].itertuples():
                    g = hist.get(tr.IDfg)
                    if g is not None and (g["Season"] == t).any():
                        cases.append((t + 1, g, models, t, tr.WAR))
            rows = []
            for w in weight_options:
                S.SEASON_WEIGHTS = w
                for reg in reg_options[kind]:
                    early, late = [], []
                    for season, g, models, t, actual in cases:
                        err = actual - project(g, kind, models, t, 1, reg=reg)["war"][0]
                        (late if season >= split_season else early).append(err)
                    rms = lambda e: float(np.sqrt(np.mean(np.square(e)))) if e else np.nan
                    rows.append({"weights (recent first)": "/".join(map(str, w)), "regression amount": reg,
                                 "picked-on RMSE": rms(early), "confirmed RMSE": rms(late),
                                 "current setting": "<--" if (w == original and reg == cfg["reg"]) else ""})
            S.SEASON_WEIGHTS = original
            out = pd.DataFrame(rows).sort_values("picked-on RMSE")
            print(f"\n{cfg['label']}s ({len(cases)} player-seasons): best 6 by the picking seasons, plus your current setting")
            show = pd.concat([out.head(6), out[out["current setting"] == "<--"]]).drop_duplicates()
            print(show.round(3).to_string(index=False))
            best, cur = out.iloc[0], out[out["current setting"] == "<--"].iloc[0]
            print(f"Best picked: weights {best['weights (recent first)']}, regression {best['regression amount']}: "
                  f"confirmed RMSE {best['confirmed RMSE']:.3f} vs {cur['confirmed RMSE']:.3f} for your current setting.")
            print("Only adopt it if the confirmed number improves too, and by more than a rounding error.")
    finally:
        S.SEASON_WEIGHTS = original

class Tee:
    """Prints to the screen and saves the same text to a file."""
    def __init__(self, path):
        self.file = open(path, "w", encoding="utf-8")
        self.screen = sys.stdout

    def write(self, text):
        self.screen.write(text)
        self.file.write(text)

    def flush(self):
        self.screen.flush()
        self.file.flush()

    def close(self):
        self.file.close()

def data_checks(data):
    print(f"\n{'=' * 70}\nDATA CHECKS\n{'=' * 70}")
    for kind, cfg in KIND.items():
        df = data[kind]
        print(f"\n{cfg['label']}s: {len(df):,} player-seasons, {df['IDfg'].nunique():,} players, "
              f"seasons {df['Season'].min()}-{df['Season'].max()}")
        per = df.groupby("Season").agg(players=("IDfg", "nunique"), total_WAR=("WAR", "sum")).round(0).astype(int)
        print(per.T.to_string())
        warns = []
        counts = per["players"]
        if S.END_SEASON not in counts.index:
            warns.append(f"no rows for {S.END_SEASON}; set END_SEASON to the last season in the data")
        else:
            prev = counts.drop(S.END_SEASON).tail(3)
            if len(prev) and counts[S.END_SEASON] < 0.8 * prev.mean():
                warns.append(f"{S.END_SEASON} has {counts[S.END_SEASON]} players vs about {prev.mean():.0f} in earlier "
                             f"seasons (partial season?)")
        dup = int(df.duplicated(["IDfg", "Season"]).sum())
        if dup:
            warns.append(f"{dup} duplicate player-seasons")
        odd = df[(df["WAR"] > 12) | (df["WAR"] < -3)]
        if len(odd):
            ex = ", ".join(f"{r.Name} {r.Season} ({r.WAR:.1f})" for r in odd.head(3).itertuples())
            warns.append(f"{len(odd)} player-seasons with WAR above 12 or below -3, e.g. {ex}")
        if df["Age"].min() < 18 or df["Age"].max() > 46:
            warns.append(f"ages outside 18-46 (min {df['Age'].min()}, max {df['Age'].max()})")
        print("Checks: " + ("all passed" if not warns else ""))
        for w in warns:
            print(f"  WARNING: {w}")

def contract_checks(data):
    print(f"\n{'=' * 70}\nCONTRACT FILE CHECKS\n{'=' * 70}")
    contracts = load_contracts()
    if contracts is None:
        return None
    tbl, skipped = build_contract_table(data, contracts, verbose=False)
    print(f"Rows in file: {len(contracts)} | usable: {len(tbl)} | skipped: {len(skipped)}")
    for nm, why in skipped:
        print(f"  skipped {nm}: {why}")
    warns = []
    dup = int(contracts.duplicated(["name", "walk_year"]).sum())
    if dup:
        warns.append(f"{dup} duplicate (name, walk_year) rows")
    if len(tbl):
        print(f"Walk years {int(tbl['walk_year'].min())}-{int(tbl['walk_year'].max())} | "
              f"hitters {int((tbl['kind'] == 'bat').sum())}, pitchers {int((tbl['kind'] == 'pit').sum())} | "
              f"average annual value ${tbl['aav'].min():.1f}M to ${tbl['aav'].max():.1f}M")
        if (tbl["walk_year"] >= S.END_SEASON).any():
            warns.append("some deals have walk_year at or after END_SEASON")
        big = tbl[tbl["aav"] > 45]
        if len(big):
            warns.append("very large average annual values (check, they pull the regression): " +
                         ", ".join(f"{r.Name} ${r.aav:.0f}M" for r in big.itertuples()))
    for w in warns:
        print(f"  WARNING: {w}")
    return tbl

def contract_time_split(tbl, min_train=20):
    """Train on earlier winters, test on the next one (what you would really do: price deals not yet signed)."""
    print(f"\n{'=' * 70}\nCONTRACT MODEL: OUT-OF-TIME TEST\n{'=' * 70}")
    print("For each winter, the model is fit ONLY on earlier winters' deals, then asked to price that winter's deals.")
    for kind, cfg in KIND.items():
        g = tbl[tbl["kind"] == kind] if tbl is not None and len(tbl) else pd.DataFrame()
        if len(g) < min_train + 5:
            print(f"\n{cfg['label']}s: not enough deals for this test ({len(g)}).")
            continue
        parts = []
        for yr in sorted(g["walk_year"].unique()):
            train, test = g[g["walk_year"] < yr], g[g["walk_year"] == yr]
            if len(train) < min_train or test.empty:
                continue
            m = fit_ols(train)
            X, _ = contract_features(test, m["use_extra"], m["use_starter"], m["median_extra"])
            pos = train[train["proj_war1"] > 0.5]
            per_war = pos["aav"].sum() / pos["proj_war1"].sum()
            parts.append(test.assign(regression=np.clip(X @ m["beta"], 0, None),
                                     war_rule=np.clip(test["proj_war1"], 0, None) * per_war,
                                     avg_baseline=train["aav"].mean()))
        if not parts:
            print(f"\n{cfg['label']}s: not enough earlier deals to train on.")
            continue
        P = pd.concat(parts)
        print(f"\n{cfg['label']}s: {len(P)} deals tested (winters {int(P['walk_year'].min())}-{int(P['walk_year'].max())})")
        rows = []
        for col, name in (("regression", "Regression model"), ("war_rule", "Implied $/WAR rule (year-1 WAR x earlier $/WAR)"),
                          ("avg_baseline", "Average AAV of earlier deals")):
            e = P["aav"] - P[col]
            rows.append({"Method": name, "RMSE $M/yr": np.sqrt((e ** 2).mean()), "MAE $M/yr": e.abs().mean(),
                         "Rank corr": P["aav"].corr(P[col], method="spearman")})
        print(pd.DataFrame(rows).round(2).to_string(index=False))
        by = P.groupby("walk_year").apply(lambda x: pd.Series({
            "Deals": len(x), "Regression RMSE": np.sqrt(((x["aav"] - x["regression"]) ** 2).mean()),
            "$/WAR rule RMSE": np.sqrt(((x["aav"] - x["war_rule"]) ** 2).mean())}))
        by["Deals"] = by["Deals"].astype(int)
        print("\nBy winter:")
        print(by.round(2).to_string())
        P = P.assign(miss=P["aav"] - P["regression"])
        worst = P.reindex(P["miss"].abs().sort_values(ascending=False).index).head(8)
        print("\nBiggest misses (average annual value, $M):")
        print(worst[["Name", "walk_year", "years", "aav", "regression", "miss"]].round(1).to_string(index=False))

def validate(data):
    data_checks(data)
    tbl = contract_checks(data)
    backtest(data)
    range_coverage(compute_error_bands(data))
    contract_time_split(tbl)
    print("\nValidation finished. Paste the key numbers into the README results table.")
