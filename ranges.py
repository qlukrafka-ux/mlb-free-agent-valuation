"""Uncertainty ranges, measured by backtesting the projections."""

import numpy as np
import pandas as pd

from .config import KIND, S
from .aging import fit_models
from .pricing import market_value
from .projection import project


def _quantile_levels():
    return (1 - S.RANGE_LEVEL) / 2, (1 + S.RANGE_LEVEL) / 2

def _tier_quantiles(r1, qlo, qhi, min_n=40):
    overall = (float(r1["resid"].quantile(qlo)), float(r1["resid"].quantile(qhi)))
    out = {}
    for tier in range(4):
        x = r1.loc[r1["tier"] == tier, "resid"]
        out[tier] = (float(x.quantile(qlo)), float(x.quantile(qhi))) if len(x) >= min_n else overall
    return out

def compute_error_bands(data):
    """
    Backtest the projections 1, 2 and 3 years ahead for every season since 2019 and record how far off they were.
    From those misses we learn: the range around a one-year projection (by projected-WAR tier), how much wider it
    gets with the horizon, how much narrower it is for veterans and wider for rookies / players who missed time,
    and how strongly one year's miss predicts the next (which sets the range for a whole contract).
    """
    bands = {}
    qlo, qhi = _quantile_levels()
    for kind, cfg in KIND.items():
        df, vol = data[kind], cfg["vol"]
        recs = []
        for t in range(S.START_SEASON + 4, S.END_SEASON):
            models = fit_models(df, kind, t)
            hist = {i: g for i, g in df[df["Season"] <= t].groupby("IDfg")}
            future = df[(df["Season"] > t) & (df["Season"] <= t + 3) & (df["Season"] != 2020)
                        & (df[vol] >= cfg["bt_min"])]
            actual = {(r.IDfg, r.Season): r.WAR for r in future.itertuples()}
            for pid, g in hist.items():
                if g["Season"].max() < t:
                    continue
                res = project(g, kind, models, t, 3)
                for k in (1, 2, 3):
                    a = actual.get((pid, t + k))
                    if a is not None:
                        recs.append((t, pid, k, res["war"][k - 1], a - res["war"][k - 1],
                                     res["limited"], res["injured"], res["veteran"]))
        if not recs:
            continue
        r = pd.DataFrame(recs, columns=["t", "pid", "k", "proj", "resid", "limited", "injured", "veteran"])
        r1 = r[r["k"] == 1].copy()
        r1["tier"] = np.digitize(r1["proj"], [1, 2.5, 4])
        tier_q = _tier_quantiles(r1, qlo, qhi)
        rmse = {k: float(np.sqrt((r.loc[r["k"] == k, "resid"] ** 2).mean()))
                for k in (1, 2, 3) if (r["k"] == k).sum() >= 40}
        mult = {1: 1.0}
        for k in (2, 3):
            mult[k] = max(1.0, rmse[k] / rmse[1]) if k in rmse and 1 in rmse else float(np.sqrt(k))
        all_rmse = float(np.sqrt((r1["resid"] ** 2).mean()))
        flag_mult = {}
        for flag, default, lo_cap, hi_cap in (("limited", 1.3, 1.0, 3.0), ("injured", 1.2, 1.0, 3.0),
                                              ("veteran", 1.0, 0.6, 1.0)):
            x = r1[r1[flag]]
            flag_mult[flag] = (float(np.clip(np.sqrt((x["resid"] ** 2).mean()) / all_rmse, lo_cap, hi_cap))
                               if len(x) >= 30 else default)
        wide = r.pivot_table(index=["t", "pid"], columns="k", values="resid")
        cors = [wide[a].corr(wide[b]) for a, b in ((1, 2), (2, 3), (1, 3))
                if a in wide and b in wide and wide[[a, b]].dropna().shape[0] >= 40]
        rho = float(np.clip(np.nanmean(cors), 0, 1)) if cors else 0.5
        bands[kind] = {"tier_q": tier_q, "mult": mult, "flag_mult": flag_mult, "rho": rho,
                       "n": int((r["k"] == 1).sum()), "recs": r}
    return bands

def war_range(bands, kind, k, war, limited=False, injured=False, veteran=False):
    """Range for the projected WAR of year k. Widens with the horizon (beyond year 3 it grows with sqrt)."""
    b = bands.get(kind) if bands else None
    if not b:
        return war, war
    q10, q90 = b["tier_q"][int(np.digitize(war, [1, 2.5, 4]))]
    m = b["mult"][k] if k in b["mult"] else b["mult"][3] * float(np.sqrt(k / 3))
    fm = b["flag_mult"]
    if limited or injured:
        m *= max(fm["limited"] if limited else 1.0, fm["injured"] if injured else 1.0)
    elif veteran:
        m *= fm.get("veteran", 1.0)
    return min(war + q10 * m, war), max(war + q90 * m, war)   # the range always contains the projection

def total_range(bands, kind, wars, lows, highs):
    """
    Range for the SUM of several years. If every year's miss were identical the ranges would simply add up;
    if they were unrelated the total would be much tighter. rho (measured in the backtest) says where in between.
    """
    b = bands.get(kind) if bands else None
    rho = b["rho"] if b else 1.0

    def combine(d):
        d = np.array(d, float)
        return float(np.sqrt(max((d ** 2).sum() + rho * (d.sum() ** 2 - (d ** 2).sum()), 0.0)))

    tot = float(sum(wars))
    return tot - combine([w - lo for w, lo in zip(wars, lows)]), tot + combine([hi - w for w, hi in zip(wars, highs)])

def project_with_ranges(p, kind, models, bands, horizon, vol1=None, pos=None):
    res = project(p, kind, models, S.END_SEASON, horizon, vol1=vol1, pos=pos)
    if res is None:
        return None
    pairs = [war_range(bands, kind, k, w, res["limited"], res["injured"], res["veteran"])
             for k, w in enumerate(res["war"], start=1)]
    res["war_low"] = [x[0] for x in pairs]
    res["war_high"] = [x[1] for x in pairs]
    res["total_low"], res["total_high"] = total_range(bands, kind, res["war"], res["war_low"], res["war_high"])
    return res

def contract_value_range(res, years, kind=None):
    """Market-rate (A) value of the contract with a range that uses the whole-contract WAR range."""
    mv = market_value(res["war"], years, kind=kind)
    lo_y, hi_y = market_value(res["war_low"], years, kind=kind), market_value(res["war_high"], years, kind=kind)
    v, v_lo_y, v_hi_y = sum(mv), sum(lo_y), sum(hi_y)
    tot, sum_lo, sum_hi = sum(res["war"]), sum(res["war_low"]), sum(res["war_high"])
    f_lo = (tot - res["total_low"]) / (tot - sum_lo) if tot - sum_lo > 1e-9 else 1.0
    f_hi = (res["total_high"] - tot) / (sum_hi - tot) if sum_hi - tot > 1e-9 else 1.0
    return v, v - f_lo * (v - v_lo_y), v + f_hi * (v_hi_y - v)

def range_coverage(bands):
    """Honesty check: build the ranges from earlier seasons, then see how often later outcomes land inside."""
    print(f"\n{'=' * 70}\nRANGE CALIBRATION (do the ranges mean what they say?)\n{'=' * 70}")
    qlo, qhi = _quantile_levels()
    pct = int(round(S.RANGE_LEVEL * 100))
    for kind, cfg in KIND.items():
        b = bands.get(kind)
        if not b:
            continue
        r1 = b["recs"][b["recs"]["k"] == 1].copy()
        r1["tier"] = np.digitize(r1["proj"], [1, 2.5, 4])
        seasons = sorted(r1["t"].unique())
        if len(seasons) < 4:
            continue
        split = seasons[len(seasons) // 2]
        train, test = r1[r1["t"] < split], r1[r1["t"] >= split]
        tq = _tier_quantiles(train, qlo, qhi)
        inside = [tq[tier][0] <= resid <= tq[tier][1] for tier, resid in zip(test["tier"], test["resid"])]
        print(f"{cfg['label']}s: ranges built from projections made before {split}; of {len(test)} later "
              f"player-seasons, {np.mean(inside):.0%} landed inside the {pct}% range (target: {pct}%).")
        print(f"   Whole-contract ranges use rho = {b['rho']:.2f} (1.00 would mean every year's miss is identical).")
        fm = b["flag_mult"]
        print(f"   Width multipliers: veterans x{fm['veteran']:.2f}, rookies/limited history x{fm['limited']:.2f}, "
              f"missed time x{fm['injured']:.2f}.")
