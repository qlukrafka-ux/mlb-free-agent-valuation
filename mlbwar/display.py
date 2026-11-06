"""Printing a player result and comparing two players."""

import numpy as np
import pandas as pd

from .config import COMPONENTS, KIND, S
from .pricing import market_value, price_lines, price_per_win
from .ranges import contract_value_range, project_with_ranges
from .contracts import predict_contract, verdict
from .charts import save_compare_chart


def show_player(data, models, contract_models, bands, kind, idfg, years, offer=None, vol1=None, pos=None):
    df = data[kind]
    cfg = KIND[kind]
    p = df[df["IDfg"] == idfg]
    res = project_with_ranges(p, kind, models[kind], bands, years, vol1, pos)
    name = p.sort_values("Season")["Name"].iloc[-1]
    pct = int(round(S.RANGE_LEVEL * 100))

    mv = market_value(res["war"], years, kind=kind)
    total_war = sum(res["war"])
    total_val, val_lo, val_hi = contract_value_range(res, years, kind)
    total_b = aav_b = None
    if kind in contract_models:
        aav_b, total_b = predict_contract(contract_models[kind], res, years)

    line = "=" * 66
    tag = f"{cfg['label']}, age {res['age_now']:.0f} in {S.END_SEASON}"
    if res["pos_group"]:
        tag += f", position group {res['pos_group']}"
    print(f"\n{line}\n{name}  ({tag})\n{line}")

    print(f"AT A GLANCE ({years}-year deal)")
    print(f"  Projected WAR:         {total_war:.1f} total, {total_war / years:.1f} per season "
          f"(likely {res['total_low'] / years:.1f} to {res['total_high'] / years:.1f} per season)")
    print(f"  Market-rate value (A): ${total_val:,.0f}M (range ${val_lo:,.0f}M to ${val_hi:,.0f}M)")
    print(f"  Regression value (B):  " + (f"${total_b:,.0f}M" if total_b is not None else "not available (no contracts model)"))
    if offer:
        extra = f"; {verdict(offer, total_b)} vs (B)" if total_b is not None else ""
        print(f"  Your offer:            ${offer:,.0f}M -> {verdict(offer, total_val)} vs (A){extra}")
    print("-" * 66)

    hist = p[p["Season"] > S.END_SEASON - 3].sort_values("Season")
    print("Recent seasons:")
    print(hist[["Season", "Age", cfg["vol"], "WAR"]].round(1).to_string(index=False))
    if res["pos_group"]:
        print(f"Position group {res['pos_group']} is inferred from his positional adjustment "
              f"(press p after the results to change it).")
    if res["pt_note"]:
        print(f"Note: {res['pt_note']}.")
    if res["limited"]:
        print("Note: limited MLB history, so the range below is wider than usual.")
    if res["injured"]:
        print("Note: he missed time recently, so the range below is wider than usual.")

    table = pd.DataFrame({
        "Season": res["season"], "Age": res["age"],
        cfg["vol"]: np.round(res["vol"]), "Proj WAR": np.round(res["war"], 2),
        f"{pct}% range": [f"{lo:.1f} to {hi:.1f}" for lo, hi in zip(res["war_low"], res["war_high"])],
        f"Value @ ${price_per_win(kind):.1f}M/WAR ($M)": np.round(mv, 1),
    })
    print(f"\nProjection ({years} years):")
    print(table.to_string(index=False))

    if res["method"] == "components" and res["comp"]:
        c = res["comp"][0]
        parts = ", ".join(f"{COMPONENTS[k]['label']} {v:+.1f}" for k, v in c.items())
        print(f"\nWhere his first-year WAR rate comes from (WAR per {cfg['rate_base']} PA): {parts} = {res['rate'][0]:.1f}")

    print(f"\n(A) Market-rate value: {total_war:.1f} WAR (range {res['total_low']:.1f} to {res['total_high']:.1f}) "
          f"-> ${total_val:,.0f}M total (range ${val_lo:,.0f}M to ${val_hi:,.0f}M), ${total_val / years:,.1f}M per year")
    if total_b is not None:
        m = contract_models[kind]
        print(f"(B) Regression value:  ${total_b:,.0f}M total, ${aav_b:,.1f}M per year, typical miss +/-${m['rmse_loo']:.1f}M per year "
              f"(fit on {m['n']} contracts, out-of-sample R^2={m['r2_loo']:.2f})")
    else:
        print("(B) Regression value:  not available (no contracts.csv model)")

    if offer:
        print(f"\n--- Your offer: ${offer:,.1f}M over {years} years (${offer / years:,.1f}M per year) ---")
        if total_war > 0:
            print(f"Cost per projected WAR: ${offer / total_war:,.1f}M (price of a win used: ${price_per_win(kind):.1f}M)")
        factor = sum((1 + S.WAR_PRICE_INFLATION) ** i for i in range(years)) / years
        need = offer / (price_per_win(kind) * factor)
        print(f"Break-even: he needs about {need:.1f} WAR over the deal to justify it "
              f"(projected: {total_war:.1f}, range {res['total_low']:.1f} to {res['total_high']:.1f})")
        print(f"(A) vs market-rate value (${total_val:,.0f}M): {verdict(offer, total_val)}; "
              f"surplus {total_val - offer:+,.0f}M")
        if total_b is not None:
            print(f"(B) vs regression value  (${total_b:,.0f}M): {verdict(offer, total_b)}; "
                  f"surplus {total_b - offer:+,.0f}M")
        where = ("below the bottom of" if offer < val_lo else "above the top of" if offer > val_hi else "inside")
        print(f"Your offer is {where} the (A) range (${val_lo:,.0f}M to ${val_hi:,.0f}M).")

    print("\nPRICE SENSITIVITY")
    for ln in price_lines(res, years, kind, offer):
        print("  " + ln)
    return res

def compare_players(data, models, contract_models, bands, h1, h2, years):
    items = []
    for kind, pid, nm, _ in (h1, h2):
        p = data[kind][data[kind]["IDfg"] == pid]
        res = project_with_ranges(p, kind, models[kind], bands, years)
        v, vlo, vhi = contract_value_range(res, years, kind)
        b = predict_contract(contract_models[kind], res, years)[1] if kind in contract_models else None
        items.append({"name": nm, "kind": kind, "p": p, "res": res, "v": v, "vlo": vlo, "vhi": vhi, "b": b})
    pct = int(round(S.RANGE_LEVEL * 100))
    n1, n2 = items[0]["name"], items[1]["name"]
    line = "=" * 66
    print(f"\n{line}\nCOMPARISON ({years} years): {n1} vs {n2}\n{line}")
    rows = {}
    for it in items:
        r = it["res"]
        rows[it["name"]] = {
            "Type / position": KIND[it["kind"]]["label"] + (f", {r['pos_group']}" if r["pos_group"] else ""),
            f"Age in {r['season'][0]}": r["age"][0],
            "Year-1 WAR": f"{r['war'][0]:.1f} ({r['war_low'][0]:.1f} to {r['war_high'][0]:.1f})",
            f"Total WAR ({pct}% range)": f"{sum(r['war']):.1f} ({r['total_low']:.1f} to {r['total_high']:.1f})",
            "WAR per season": f"{sum(r['war']) / years:.1f}",
            "Market-rate value (A)": f"${it['v']:,.0f}M (${it['vlo']:,.0f}M to ${it['vhi']:,.0f}M)",
            "Regression value (B)": f"${it['b']:,.0f}M" if it["b"] is not None else "n/a",
            "Price of a win used": f"${price_per_win(it['kind']):.1f}M",
        }
    print(pd.DataFrame(rows).to_string())
    seasons = items[0]["res"]["season"]
    by_year = pd.DataFrame({"Season": seasons})
    for it in items:
        r = it["res"]
        by_year[it["name"]] = [f"{w:.1f} ({lo:.1f} to {hi:.1f})" for w, lo, hi in zip(r["war"], r["war_low"], r["war_high"])]
    print("\nBy season:")
    print(by_year.to_string(index=False))
    t1, t2 = sum(items[0]["res"]["war"]), sum(items[1]["res"]["war"])
    lo1, hi1, lo2, hi2 = (items[0]["res"]["total_low"], items[0]["res"]["total_high"],
                          items[1]["res"]["total_low"], items[1]["res"]["total_high"])
    lead, trail = (n1, n2) if t1 >= t2 else (n2, n1)
    overlap = max(lo1, lo2) <= min(hi1, hi2)
    print(f"\nBottom line: {lead} projects {abs(t1 - t2):.1f} more WAR over {years} years than {trail}. "
          + ("The ranges overlap, so the model cannot separate them with confidence." if overlap
             else "The ranges do not overlap, so the gap is larger than the model's usual uncertainty."))
    path = save_compare_chart(items, years)
    if path:
        print(f"Chart saved: {path}")
