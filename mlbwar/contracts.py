"""Contract file, regression model and predictions."""

import os
import numpy as np
import pandas as pd

from .config import BASE_DIR, CONTRACT_FILE, DEFAULT_CONTRACTS, KIND, S
from .util import fold, norm_kind, parse_money, parse_years
from .aging import _cache, get_models
from .pricing import estimate_price_per_win
from .projection import project


def find_contract_file():
    """Look for the contracts file next to this script first, then in the folder you ran Python from."""
    for folder in (BASE_DIR, os.getcwd()):
        for name in (CONTRACT_FILE, "contract.csv", "contracts.csv.txt", "contracts.txt"):
            path = os.path.join(folder, name)
            if os.path.exists(path):
                return path
    return None

def load_contracts():
    path = find_contract_file()
    if path is None:
        path = os.path.join(BASE_DIR, CONTRACT_FILE)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(DEFAULT_CONTRACTS)
        n = DEFAULT_CONTRACTS.count("\n") - 1
        print(f"  No contracts file found, so I created one with {n} real free-agent deals:")
        print(f"  {path}")
        print("  Open it to add or fix deals (columns: Name, kind, walk_year, years, total_value_m).")
    else:
        print(f"  Using contracts file: {path}")
    try:
        c = pd.read_csv(path, dtype=str, sep=None, engine="python", encoding="utf-8-sig")
    except Exception as e:
        print(f"  Couldn't read {path}: {e}")
        return None
    c.columns = [x.strip().lower() for x in c.columns]
    c = c.apply(lambda col: col.str.strip() if col.dtype == object else col)
    needed = ["name", "kind", "walk_year", "years", "total_value_m"]
    missing = [x for x in needed if x not in c.columns]
    if missing:
        print(f"  The contracts file is missing columns {missing}. Columns found: {list(c.columns)}")
        print(f"  It needs exactly: {needed}")
        return None
    return c

def build_contract_table(data, contracts, verbose=True):
    """One row per usable contract: what the model projected for the player the day he signed."""
    rows, skipped = [], []
    for _, c in contracts.iterrows():
        nm = str(c["name"]).strip()
        kind = norm_kind(c["kind"])
        total = parse_money(c["total_value_m"])
        yrs = parse_years(c["years"])
        try:
            walk = int(float(str(c["walk_year"]).strip()))
        except ValueError:
            walk = None
        reason = None
        if kind is None or total is None or yrs is None or walk is None:
            reason = "couldn't read kind / walk_year / years / total_value_m"
        else:
            df = data[kind]
            ids = df.loc[df["fold"] == fold(nm), "IDfg"].unique()
            if len(ids) != 1:
                reason = "name not found (or ambiguous) in the data"
            else:
                models = get_models(data, kind, walk)
                res = project(df[df["IDfg"] == ids[0]], kind, models, walk, int(yrs))
                if res is None:
                    reason = "no data in the 3 seasons before the deal"
        if reason:
            skipped.append((nm, reason))
            if verbose:
                print(f"  Skipping '{nm}': {reason}.")
            continue
        rows.append({"Name": nm, "kind": kind, "walk_year": walk, "proj_war1": res["war"][0],
                     "age": res["age_now"] + 1, "years": float(yrs), "extra": res["extra"],
                     "aav": total / yrs, "total": total,
                     "wsum": sum(max(w, 0) * (1 + S.WAR_PRICE_INFLATION) ** i for i, w in enumerate(res["war"])),
                     "starter": float(res["starter"]) if res["starter"] is not None else np.nan})
    return pd.DataFrame(rows), skipped

def contract_features(g, use_extra, use_starter, med):
    names = ["intercept", "proj_war1", "age", "years", "walk_year"]
    cols = [np.ones(len(g)), g["proj_war1"], g["age"], g["years"], g["walk_year"] - S.END_SEASON]
    if use_extra:
        names.append("extra_stat")
        cols.append(g["extra"].fillna(med))
    if use_starter:
        names.append("is_starter")
        cols.append(g["starter"].fillna(0))
    return np.column_stack(cols), names

def fit_ols(g):
    """Ordinary least squares: average annual value ($M) on the contract features."""
    use_extra = bool(g["extra"].notna().any())          # pitchers have no extra stat in B-Ref data
    use_starter = bool(g["starter"].notna().any())      # pitchers only: starter vs reliever
    med = float(g["extra"].median()) if use_extra else 0.0
    X, names = contract_features(g, use_extra, use_starter, med)
    y = g["aav"].to_numpy()
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ beta
    ss_tot = ((y - y.mean()) ** 2).sum()
    r2 = 1 - ((y - pred) ** 2).sum() / ss_tot
    # leave-one-out check: how well does it predict a deal it did NOT see?
    hat = np.einsum("ij,ji->i", X, np.linalg.pinv(X))
    loo = (y - pred) / np.clip(1 - hat, 1e-6, None)
    return {"beta": beta, "names": names, "median_extra": med, "r2": r2,
            "r2_loo": 1 - (loo ** 2).sum() / ss_tot, "rmse_loo": float(np.sqrt((loo ** 2).mean())),
            "n": len(g), "use_extra": use_extra, "use_starter": use_starter}

def fit_contract_models(data):
    contracts = load_contracts()
    if contracts is None:
        return {}
    tbl, _ = build_contract_table(data, contracts)
    _cache["contract_table"] = tbl
    for kind, info in estimate_price_per_win(tbl).items():
        print(f"  Price of a win for {KIND[kind]['label'].lower()}s, measured from {info['n']} deals "
              f"(winters {info['recent'][0]}-{info['recent'][-1]}): ${info['price']:.1f}M")
    out = {}
    if tbl.empty:
        return out
    for kind, g in tbl.groupby("kind"):
        if len(g) < 8:
            print(f"  Only {len(g)} usable {KIND[kind]['label'].lower()} contracts; need at least 8. Skipping.")
            continue
        m = fit_ols(g)
        out[kind] = m
        print(f"  {KIND[kind]['label']} contract model: n={m['n']}, R^2={m['r2']:.2f}, "
              f"out-of-sample (leave-one-out) R^2={m['r2_loo']:.2f}, typical miss ${m['rmse_loo']:.1f}M per year")
        print("    Average annual value ($M) = " + " + ".join(f"{b:.2f}*{n}" for b, n in zip(m["beta"], m["names"])))
    return out

def predict_contract(model, res, years):
    x = [1, res["war"][0], res["age_now"] + 1, years, 0.0]      # walk_year term is 0 = current market (END_SEASON)
    if model["use_extra"]:
        x.append(res["extra"] if not pd.isna(res["extra"]) else model["median_extra"])
    if model["use_starter"]:
        x.append(1.0 if res["starter"] else 0.0)
    aav = max(float(np.array(x) @ model["beta"]), 0.0)
    return aav, aav * years

def verdict(offer, value):
    if value <= 0:
        return "the model sees no value"
    ratio = offer / value
    if ratio < 0.9:
        return f"BARGAIN: offer is {100 * (1 - ratio):.0f}% below modeled value"
    if ratio > 1.1:
        return f"OVERPAY: offer is {100 * (ratio - 1):.0f}% above modeled value"
    return "roughly FAIR (within 10% of modeled value)"
