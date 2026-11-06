"""Free-agent class report (CSV, markdown, chart)."""

import datetime
import os
import numpy as np
import pandas as pd

from .config import BASE_DIR, DEFAULT_FREE_AGENTS, KIND, REPORT_DIR, S
from .util import fold, norm_kind, norm_pos, parse_money, parse_years
from .data import find_player
from .pricing import market_value, price_per_win, price_source
from .projection import project
from .ranges import contract_value_range, project_with_ranges
from .contracts import predict_contract
from .charts import save_class_chart


def export_projections(data, models, kind, horizon=5):
    df = data[kind]
    rows = []
    for _, g in df[df["Season"] > S.END_SEASON - 3].groupby("IDfg"):
        if g["Season"].max() < S.END_SEASON - 1:   # skip players with no recent playing time
            continue
        res = project(g, kind, models, S.END_SEASON, horizon)
        if res is None:
            continue
        mv = market_value(res["war"], horizon, kind=kind)
        rows.append({"Name": g.sort_values("Season")["Name"].iloc[-1],
                     f"Age_{S.END_SEASON + 1}": res["age"][0],
                     f"WAR_{S.END_SEASON + 1}": round(res["war"][0], 2),
                     f"WAR_next{horizon}_total": round(sum(res["war"]), 2),
                     f"Market_value_{horizon}yr_$M": round(sum(mv), 1)})
    out = pd.DataFrame(rows).sort_values(f"WAR_{S.END_SEASON + 1}", ascending=False)
    path = os.path.join(BASE_DIR, f"projections_{kind}.csv")
    out.to_csv(path, index=False)
    print(f"Saved {len(out)} {KIND[kind]['label'].lower()} projections to {path}")

def default_contract_years(age):
    for max_age, yrs in S.YEARS_BY_AGE:
        if age <= max_age:
            return yrs
    return 2

def find_free_agent_file(path=None):
    if path and os.path.exists(path):
        return path
    for folder in (BASE_DIR, os.getcwd()):
        p = os.path.join(folder, "free_agents.csv")
        if os.path.exists(p):
            return p
    return None

def free_agent_report(data, models, contract_models, bands, path=None):
    import csv
    path = find_free_agent_file(path)
    if path is None:
        path = os.path.join(BASE_DIR, "free_agents.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Name", "kind", "years", "expected_vol", "est_total_m", "note"])
            for nm, kd, note in DEFAULT_FREE_AGENTS:
                w.writerow([nm, kd, "", "", "", note])
        print(f"No free_agents.csv found, so I created a STARTER list: {path}")
        print("Confirm it against MLB Trade Rumors' official list and edit it. Optional columns: years, "
              "expected_vol (PA or IP next season), est_total_m (a public contract estimate to compare against).")
    fa = pd.read_csv(path, dtype=str, sep=None, engine="python", encoding="utf-8-sig")
    fa.columns = [c.strip().lower() for c in fa.columns]
    if "name" not in fa.columns:
        print("free_agents.csv needs a 'Name' column.")
        return
    rows = []
    for _, r in fa.iterrows():
        nm = str(r["name"]).strip()
        kind_hint = norm_kind(r["kind"]) if "kind" in fa.columns and isinstance(r.get("kind"), str) else None
        hits = [h for h in find_player(data, nm, recent=S.END_SEASON - 2) if kind_hint in (None, h[0])]
        exact = [h for h in hits if fold(h[2]) == fold(nm)]
        hits = exact or hits
        if len(hits) != 1:
            print(f"  Skipping '{nm}': {'not found in the last 3 seasons of data' if not hits else 'matches several players, add the kind column'}.")
            continue
        kind, pid = hits[0][0], hits[0][1]
        p = data[kind][data[kind]["IDfg"] == pid]
        vol1 = None
        if "expected_vol" in fa.columns and isinstance(r.get("expected_vol"), str) and r["expected_vol"].strip():
            try:
                vol1 = float(r["expected_vol"].replace(",", ""))
            except ValueError:
                vol1 = None
        probe = project(p, kind, models[kind], S.END_SEASON, 1)
        yrs = parse_years(r["years"]) if "years" in fa.columns and isinstance(r.get("years"), str) else None
        yrs = yrs or default_contract_years(probe["age_now"] + 1)
        pos_override = norm_pos(r["pos"]) if "pos" in fa.columns and isinstance(r.get("pos"), str) and r["pos"].strip() else None
        res = project_with_ranges(p, kind, models[kind], bands, yrs, vol1, pos_override if kind == "bat" else None)
        mv, mv_lo, mv_hi = contract_value_range(res, yrs, kind)
        total_b = np.nan
        if kind in contract_models:
            total_b = predict_contract(contract_models[kind], res, yrs)[1]
        est = parse_money(r["est_total_m"]) if "est_total_m" in fa.columns and isinstance(r.get("est_total_m"), str) else None
        flags = "; ".join(x for x in (res["pt_note"], "wider range (limited history)" if res["limited"] else "",
                                       "wider range (missed time)" if res["injured"] else "") if x)
        rows.append({"Name": hits[0][2], "Type": KIND[kind]["label"], "Pos": res["pos_group"] or "P",
                     "Age_next": res["age"][0], "Years": yrs,
                     "WAR_yr1": round(res["war"][0], 1), "WAR_total": round(sum(res["war"]), 1),
                     "WAR_low": round(res["total_low"], 1), "WAR_high": round(res["total_high"], 1),
                     "A_value_$M": round(mv), "A_low_$M": round(mv_lo), "A_high_$M": round(mv_hi),
                     "B_regression_$M": round(total_b) if not np.isnan(total_b) else np.nan,
                     "Estimate_$M": est if est else np.nan,
                     "A_minus_est_$M": round(mv - est) if est else np.nan,
                     "B_minus_est_$M": round(total_b - est) if est and not np.isnan(total_b) else np.nan,
                     "Notes": flags})
    if not rows:
        print("No players could be projected.")
        return
    out = pd.DataFrame(rows).sort_values("A_value_$M", ascending=False)
    os.makedirs(REPORT_DIR, exist_ok=True)
    out_path = os.path.join(REPORT_DIR, "free_agent_class_report.csv")
    md_path = os.path.join(REPORT_DIR, "free_agent_class_report.md")
    out.to_csv(out_path, index=False)
    write_markdown_report(out, md_path)
    chart_path = save_class_chart(out, os.path.join(REPORT_DIR, "free_agent_class_chart.png"))
    show = ["Name", "Pos", "Age_next", "Years", "WAR_total", "WAR_low", "WAR_high", "A_value_$M", "B_regression_$M"]
    print(f"\nFree-agent class ({len(out)} players), sorted by market-rate value (A):\n")
    print(out[show].to_string(index=False))
    print(f"\nSaved: {out_path}\n       {md_path}  (a formatted table you can paste into your write-up or GitHub)"
          + (f"\n       {chart_path}" if chart_path else ""))
    print("A = WAR x $/WAR; B = regression on past free-agent deals. WAR_low/high are the whole-contract range (see RANGE_LEVEL). "
          "A new labor agreement could change prices, and the model assumes today's market.")

def write_markdown_report(out, path):
    pct = int(round(S.RANGE_LEVEL * 100))
    lines = [f"# Free-agent class projections", "",
             f"*Generated {datetime.date.today():%B %d, %Y} by war_model.py. Seasons through {S.END_SEASON}. "
             f"Ranges cover {pct}% of past outcomes.*", "",
             "| Player | Pos | Age | Years | Projected WAR (range) | Market-rate value $M (range) | Regression value $M | Notes |",
             "|---|---|---|---|---|---|---|---|"]
    for d in out.to_dict("records"):
        b = "" if pd.isna(d["B_regression_$M"]) else f"{d['B_regression_$M']:,.0f}"
        lines.append(f"| {d['Name']} | {d['Pos']} | {d['Age_next']} | {d['Years']} | "
                     f"{d['WAR_total']:.1f} ({d['WAR_low']:.1f} to {d['WAR_high']:.1f}) | "
                     f"{d['A_value_$M']:,.0f} ({d['A_low_$M']:,.0f} to {d['A_high_$M']:,.0f}) | {b} | {d['Notes']} |")
    lines += ["", f"**Method:** Baseball-Reference WAR, projected with age curves, regression to the mean and "
              f"position-aware components for hitters. Market-rate value = WAR x the price of a win "
              f"(${price_per_win('bat'):.1f}M for hitters, ${price_per_win('pit'):.1f}M for pitchers; "
              f"{price_source('bat')}; growing {S.WAR_PRICE_INFLATION:.0%} a year); regression value is fit to past free-agent deals. "
              "Contract length is assumed by age unless set in free_agents.csv. "
              "The labor agreement expires this winter, so prices may change.", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
