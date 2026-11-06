"""Projecting a player: rate, playing time, rookies and missed time."""

import numpy as np

from .config import COMPONENTS, KIND, POS_CLASS, POS_DEFAULT_RUNS, RUNS_PER_WIN, S


def _role_volume(r, kind):
    """Full-season playing time implied by a rookie's role: PA per game x games, or IP per start x starts."""
    try:
        if kind == "bat":
            g, pa = float(r["G"]), float(r["PA"])
            if g >= 20 and pa / g >= S.ROLE_MIN_PA_PER_G:
                return pa / g * S.FULL_SEASON_GAMES
        else:
            g, gs, ip = float(r["G"]), float(r["GS"]), float(r["IP"])
            if gs >= 5 and gs / g >= 0.5:
                return ip / gs * S.STARTS_PER_SEASON
            if g >= 15 and gs / g < 0.5:
                return ip / g * S.RELIEF_APPEARANCES
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        pass
    return None

def project(p, kind, models, end_season, horizon, reg=None, special=None, vol1=None, method=None, pos=None):
    """
    p = all rows for one player. Projects the seasons after `end_season`.
    Steps: age-adjust each of the last 3 seasons to his current age, take a weighted average, regress toward
    the league mean, then age the rate and playing time forward. For hitters (method='components') this is done
    separately for batting, baserunning, fielding and the positional adjustment, then added back together.
    """
    cfg = KIND[kind]
    vol = cfg["vol"]
    special = S.USE_SPECIAL_CASES if special is None else special
    method = S.HITTER_MODEL if method is None else method
    p = p[(p["Season"] <= end_season) & (p["Season"] > end_season - 3)]
    p = p.sort_values("Season", ascending=False)
    if p.empty:
        return None

    last = p.iloc[0]
    age_now = float(last["Age"] + (end_season - last["Season"]))
    vol_by_back = {int(end_season - r["Season"]): r[vol] for _, r in p.iterrows()}

    use_comp = (kind == "bat" and method == "components" and "comp" in models
                and "r_bat" in p.columns and bool(p["r_bat"].notna().all()))
    pgrp = None
    comp_val = comp_curve = None
    if use_comp:
        last_grp = last["pgrp"] if isinstance(last.get("pgrp"), str) else "2B/3B/CF"
        pgrp = pos if pos in POS_CLASS else last_grp
        pcls = POS_CLASS[pgrp]
        comp_val, comp_curve = {}, {}
        reg_scale = 1.0 if reg is None else reg / cfg["reg"]     # reg=0 turns regression to the mean off everywhere
        for name, spec in COMPONENTS.items():
            m = models["comp"][name]
            curve = m["curves"][pcls]
            prior = m["priors"].get(pgrp, m["priors"]["_all"])
            num = den = 0.0
            for _, r in p.iterrows():
                back = int(end_season - r["Season"])
                shift = sum(curve(r["Age"] + j) for j in range(back))      # age-adjust to now
                w = S.SEASON_WEIGHTS[back] * r[vol]
                num += w * (r[spec["col"]] + shift)
                den += w
            r_amt = spec["reg"] * reg_scale
            comp_val[name] = (num + r_amt * prior) / (den + r_amt)
            comp_curve[name] = curve
        if pgrp != last_grp:      # he is expected to play elsewhere: use that position's typical adjustment
            comp_val["pos"] = models["comp"]["pos"]["priors"].get(pgrp, POS_DEFAULT_RUNS[pgrp] / RUNS_PER_WIN)
        base_rate = sum(comp_val.values())
    else:
        num = den = 0.0
        for _, r in p.iterrows():
            back = int(end_season - r["Season"])
            shift = sum(models["rate"](r["Age"] + j) for j in range(back))   # age-adjust to now
            w = S.SEASON_WEIGHTS[back] * r[vol]
            num += w * (r["rate"] + shift)
            den += w
        reg_amt = cfg["reg"] if reg is None else reg
        base_rate = (num + reg_amt * models["prior"]) / (den + reg_amt)

    v0, v1 = vol_by_back.get(0, 0.0), vol_by_back.get(1, 0.0)
    if kind == "bat":
        volume = 0.5 * v0 + 0.1 * v1 + 200
        starter = None
    else:
        starter = p["GS"].sum() / max(p["G"].sum(), 1) >= 0.5
        volume = 0.5 * v0 + 0.1 * v1 + (60 if starter else 25)

    # ---- special cases: rookies / call-ups and players who missed time
    total_vol = sum(vol_by_back.values())
    prev = [vol_by_back[b] for b in (1, 2) if b in vol_by_back]
    best_prev = max(prev) if prev else 0.0
    limited = injured = False
    note = ""
    if special:
        if total_vol <= cfg["rookie_vol"]:
            limited = True
            role = _role_volume(last, kind)
            if role and role > volume:
                volume, note = role, "limited MLB history: playing time projected from his role"
        elif best_prev >= cfg["heal_min"] and v0 < 0.6 * best_prev:
            injured = True
            healthy = [v for v in vol_by_back.values() if v >= 0.7 * best_prev]
            back_pt = S.RETURN_FACTOR * float(np.mean(healthy))
            note = "missed time last year"
            if back_pt > volume:
                volume, note = back_pt, "missed time last year: playing time set from his healthy seasons"
    veteran = (not limited) and (not injured) and total_vol >= 1.5 * cfg["rookie_vol"]
    if vol1 is not None:
        volume, note = float(vol1), "playing time set by you"
    volume = min(volume, cfg["vol_cap"])

    rate, age = base_rate, age_now
    out = {"season": [], "age": [], "vol": [], "rate": [], "war": [], "comp": []}
    for k in range(horizon):
        if use_comp:
            for name in comp_val:
                comp_val[name] += comp_curve[name](age)                   # age -> age + 1
            rate = sum(comp_val.values())
            out["comp"].append(dict(comp_val))
        else:
            rate += models["rate"](age)
        if k > 0:
            ratio = models["vol"](age)
            if age >= 30:
                ratio = min(ratio, 1.0)                   # guard against survivor bias: no PT gains after 30
            volume = min(volume * ratio, cfg["vol_cap"])
        age += 1
        out["season"].append(end_season + 1 + k)
        out["age"].append(int(round(age)))
        out["vol"].append(volume)
        out["rate"].append(rate)
        out["war"].append(rate * volume / cfg["rate_base"])

    out["age_now"] = age_now
    out["extra"] = last[cfg["extra"]] if cfg["extra"] in p.columns else np.nan
    out["starter"] = starter
    out["limited"], out["injured"], out["veteran"], out["pt_note"] = limited, injured, veteran, note
    out["pos_group"] = pgrp
    out["method"] = "components" if use_comp else "total"
    return out
