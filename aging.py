"""Aging curves and the fitted models (the "delta method")."""

import numpy as np

from .config import COMPONENTS, KIND, S


def fit_curve(df, col, mode, cfg, upto, cls=None, impute=False, dropout_weight=None):
    """
    Delta method: compare each player's season to his next season (age a -> a+1),
    then fit a smooth quadratic through the average change at each age.
      mode='diff'  -> change in the value (used for WAR rate)
      mode='ratio' -> next/current (used for playing time)
    Survivor-bias fix (impute=True): players who vanish from the data after a season are counted as if they had
    dropped to replacement level (at weight DROPOUT_WEIGHT), so the curve isn't built only from players who
    were good enough to keep their jobs.
    Returns f(age) = expected change going from `age` to `age + 1`.
    """
    vol = cfg["vol"]
    default = 0.0 if mode == "diff" else 1.0
    dw = S.DROPOUT_WEIGHT if dropout_weight is None else dropout_weight

    dfu = df[df["Season"] <= upto]
    d = dfu[dfu[vol] >= cfg["min_vol"]].copy()
    d["_w"] = d[vol]
    a = d[["IDfg", "Season", "Age", col, "_w"] + (["pcls"] if cls else [])]
    b = a.copy()
    b["Season"] = b["Season"] - 1                      # lines season s+1 up with season s
    p = a.merge(b, on=["IDfg", "Season"], suffixes=("", "_n"))
    p = p[(p["Age_n"] - p["Age"] == 1) & p["Age"].between(21, 40)].copy()
    if cls:
        p = p[p["pcls"] == cls].copy()                  # class of the EARLIER season, so position changes show up

    if mode == "ratio":
        p = p[p[col] > 0]
        y = (p[col + "_n"] / p[col]).clip(0.3, 2.0)
    else:
        y = p[col + "_n"] - p[col]

    if len(p) < 30:
        print(f"  Warning: only {len(p)} season pairs for '{col}' curve{' (' + cls + ')' if cls else ''}; using flat curve.")
        return lambda age: default

    x = (p["Age"] - 28).to_numpy(float)
    yv = np.asarray(y, float)
    wv = (2 / (1 / p["_w"] + 1 / p["_w_n"])).to_numpy(float)       # harmonic mean of the two samples

    if impute and mode == "diff" and dw > 0:
        repl = dfu[(dfu["rate"] <= S.REPLACEMENT_RATE) & (dfu[vol] >= cfg["qual"])]
        if len(repl) >= 50:
            fill = float(np.average(repl[col], weights=repl[vol]))
            keys = set(zip(dfu["IDfg"], dfu["Season"]))
            cand = d[(d["Season"] <= upto - 1) & d["Age"].between(21, 40)]
            if cls:
                cand = cand[cand["pcls"] == cls]
            gone = cand[[(i, s + 1) not in keys for i, s in zip(cand["IDfg"], cand["Season"])]]
            if len(gone):
                x = np.concatenate([x, (gone["Age"] - 28).to_numpy(float)])
                yv = np.concatenate([yv, fill - gone[col].to_numpy(float)])
                wv = np.concatenate([wv, dw * gone["_w"].to_numpy(float)])

    coefs = np.polyfit(x, yv, 2, w=np.sqrt(wv))
    return lambda age: float(np.polyval(coefs, np.clip(age, 21, 40) - 28))

def fit_models(df, kind, upto, dropout_weight=None):
    cfg = KIND[kind]
    recent = df[(df["Season"] <= upto) & (df["Season"] > upto - 3) & (df[cfg["vol"]] >= cfg["min_vol"])]
    prior = float(np.average(recent["rate"], weights=recent[cfg["vol"]]))
    models = {
        "rate": fit_curve(df, "rate", "diff", cfg, upto, impute=True, dropout_weight=dropout_weight),
        "vol": fit_curve(df, cfg["vol"], "ratio", cfg, upto),
        "prior": prior,
    }
    if kind == "bat" and "r_bat" in df.columns:
        comp = {}
        for name, spec in COMPONENTS.items():
            col = spec["col"]
            imp = name in ("bat", "run", "fld")           # position and replacement parts are not about skill
            if spec["by_class"]:
                curves = {c: fit_curve(df, col, "diff", cfg, upto, cls=c, impute=imp, dropout_weight=dropout_weight)
                          for c in ("premium", "middle", "corner")}
            else:
                one = fit_curve(df, col, "diff", cfg, upto, impute=imp, dropout_weight=dropout_weight)
                curves = {c: one for c in ("premium", "middle", "corner")}
            priors = {"_all": float(np.average(recent[col], weights=recent[cfg["vol"]]))}
            for grp, x in recent.groupby("pgrp"):
                if len(x) >= 30:
                    priors[grp] = float(np.average(x[col], weights=x[cfg["vol"]]))
            comp[name] = {"curves": curves, "priors": priors}
        models["comp"] = comp
    return models

_cache = {}

def get_models(data, kind, upto):
    if (kind, upto) not in _cache:
        _cache[(kind, upto)] = fit_models(data[kind], kind, upto)
    return _cache[(kind, upto)]
