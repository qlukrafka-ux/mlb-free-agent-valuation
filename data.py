"""Loading and cleaning the Baseball-Reference WAR data."""

import difflib
import os
import numpy as np
import pandas as pd

from .config import DATA_DIR, KIND, POS_CLASS, RUNS_PER_WIN, S
from .util import fold, position_group


def normalize_bref(raw, kind):
    """Convert Baseball-Reference bWAR files into the column layout the rest of the script uses."""
    df = raw.copy()
    need = ["name_common", "age", "mlb_ID", "year_ID", "WAR"] + (["PA"] if kind == "bat" else ["IPouts", "G", "GS"])
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise SystemExit(f"Baseball-Reference data is missing columns {missing}.\nColumns found: {list(df.columns)}")

    for c in ["age", "mlb_ID", "year_ID", "WAR", "PA", "IPouts", "G", "GS", "OPS_plus", "runs_bat", "runs_br",
              "runs_dp", "runs_field", "runs_position", "runs_catcher"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[(df["year_ID"] >= S.START_SEASON) & (df["year_ID"] <= S.END_SEASON)]
    df = df.dropna(subset=["mlb_ID", "age", "WAR"])

    out = pd.DataFrame({"IDfg": df["mlb_ID"].astype(int),        # player ID (MLBAM id when using B-Ref)
                        "Name": df["name_common"],
                        "Season": df["year_ID"].astype(int),
                        "Age": df["age"],
                        "WAR": df["WAR"]})
    if kind == "bat":
        if "pitcher" in df.columns:                              # drop pitchers' hitting rows
            out = out[~df["pitcher"].astype(str).str.upper().isin(["Y", "TRUE"])]
            df = df.loc[out.index]
        out["PA"] = df["PA"]
        out["G"] = df["G"] if "G" in df.columns else np.nan
        out["wRC+"] = df["OPS_plus"] if "OPS_plus" in df.columns else np.nan   # OPS+ stands in for wRC+
        if all(c in df.columns for c in ("runs_bat", "runs_br", "runs_field", "runs_position")):
            out["runs_bat"] = df["runs_bat"].fillna(0)
            out["runs_run"] = df["runs_br"].fillna(0) + (df["runs_dp"].fillna(0) if "runs_dp" in df.columns else 0)
            out["runs_fld"] = df["runs_field"].fillna(0)
            out["runs_pos"] = df["runs_position"].fillna(0)
            out["runs_cat"] = df["runs_catcher"].fillna(0) if "runs_catcher" in df.columns else 0.0
        out = out.dropna(subset=["PA"])
    else:
        out["IP"] = df["IPouts"] / 3
        out["G"] = df["G"]
        out["GS"] = df["GS"]
        out = out.dropna(subset=["IP"])
    return out

def load_raw(kind):
    """Download WAR data with pybaseball (cached to CSV so it only downloads once)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"{S.SOURCE}_{kind}_{S.START_SEASON}_{S.END_SEASON}_v3.csv")
    if os.path.exists(path):
        return pd.read_csv(path)

    from pybaseball import cache
    cache.enable()
    print(f"Downloading {KIND[kind]['label']} data from {S.SOURCE} (one time only)...")
    if S.SOURCE == "bref":
        from pybaseball import bwar_bat, bwar_pitch
        raw = bwar_bat(return_all=True) if kind == "bat" else bwar_pitch(return_all=True)
        raw = normalize_bref(raw, kind)
    else:
        from pybaseball import batting_stats, pitching_stats
        if kind == "bat":
            raw = batting_stats(S.START_SEASON, S.END_SEASON, qual=KIND[kind]["qual"])
        else:
            raw = pitching_stats(S.START_SEASON, S.END_SEASON, qual=KIND[kind]["qual"])
    raw.to_csv(path, index=False)
    return raw

def clean(raw, kind):
    """One row per player-season, with 2020 scaled up to a 162-game pace."""
    cfg = KIND[kind]
    vol = cfg["vol"]
    df = raw.copy()

    if kind == "pit":  # FanGraphs writes 180.1 to mean 180 and 1/3 innings
        whole = np.floor(df["IP"])
        df["IP"] = whole + np.round((df["IP"] - whole) * 10) / 3

    scale = np.where(df["Season"] == 2020, 162 / 60, 1.0)
    run_cols = [c for c in ("runs_bat", "runs_run", "runs_fld", "runs_pos", "runs_cat") if c in df.columns]
    for c in ["WAR", vol, "G", "GS"] + run_cols:
        if c in df.columns:
            df[c] = df[c] * scale

    agg = {"Name": "first", "Age": "max", "WAR": "sum", vol: "sum"}
    if kind == "pit":
        agg.update({"GS": "sum", "G": "sum"})
    elif "G" in df.columns:
        agg["G"] = "sum"
    for c in run_cols:
        agg[c] = "sum"
    if cfg["extra"] in df.columns:
        agg[cfg["extra"]] = "first"

    df = df.dropna(subset=["Age", "WAR", vol])
    df = df.groupby(["IDfg", "Season"], as_index=False).agg(agg)
    df = df[df[vol] >= cfg["qual"]].copy()
    df["fold"] = df["Name"].map(fold)
    df["rate"] = df["WAR"] / df[vol] * cfg["rate_base"]   # WAR per 600 PA or per 180 IP
    if kind == "bat" and len(run_cols) >= 4:
        per = cfg["rate_base"] / df[vol] / RUNS_PER_WIN       # runs -> WAR per 600 PA
        df["r_bat"] = df["runs_bat"] * per
        df["r_run"] = df["runs_run"] * per
        df["r_fld"] = df["runs_fld"] * per
        df["r_pos"] = df["runs_pos"] * per
        df["r_rest"] = df["rate"] - df[["r_bat", "r_run", "r_fld", "r_pos"]].sum(axis=1)   # replacement level + rounding
        pos_runs600 = df["runs_pos"] / df[vol] * cfg["rate_base"]
        cat = df["runs_cat"] if "runs_cat" in df.columns else pd.Series(0.0, index=df.index)
        df["pgrp"] = [position_group(x, c) for x, c in zip(pos_runs600, cat)]
        df["pcls"] = df["pgrp"].map(POS_CLASS)
    return df

def find_player(data, query, recent=None):
    q = query.lower().strip()
    hits = []
    for kind, df in data.items():
        latest = df.sort_values("Season").groupby("IDfg").tail(1)
        latest = latest[latest["Season"] >= (S.END_SEASON - 1 if recent is None else recent)]
        m = latest[latest["fold"].str.contains(fold(q), regex=False)]
        for _, r in m.iterrows():
            hits.append((kind, r["IDfg"], r["Name"], int(r["Season"])))
    exact = [h for h in hits if fold(h[2]) == fold(q)]
    return exact if exact else hits

def suggest_names(data, query):
    names = set()
    for df in data.values():
        names.update(df.loc[df["Season"] >= S.END_SEASON - 1, "Name"].unique())
    return difflib.get_close_matches(query, sorted(names), n=5, cutoff=0.6)
