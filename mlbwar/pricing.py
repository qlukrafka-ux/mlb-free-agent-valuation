"""The price of a win and the market-rate value of a contract."""


from .config import S


_price = {"bat": None, "pit": None, "table": {}}

def price_per_win(kind=None):
    """$ millions per projected win: your fixed number, else measured from the contracts, else the placeholder."""
    if isinstance(S.PRICE_PER_WIN, (int, float)) and not isinstance(S.PRICE_PER_WIN, bool):
        return float(S.PRICE_PER_WIN)
    return _price.get(kind) or S.DOLLARS_PER_WAR

def price_source(kind=None):
    if isinstance(S.PRICE_PER_WIN, (int, float)) and not isinstance(S.PRICE_PER_WIN, bool):
        return "set in the settings"
    if _price.get(kind):
        return f"measured from {_price['table'][kind]['n']} contracts"
    return "default placeholder"

def market_value(war_list, years, dollars_per_war=None, inflation=None, kind=None):
    """Contract value A: projected WAR x price of a win, the price growing each year. WAR below 0 counts as $0."""
    dpw = price_per_win(kind) if dollars_per_war is None else dollars_per_war
    g = S.WAR_PRICE_INFLATION if inflation is None else inflation
    return [max(w, 0) * dpw * (1 + g) ** i for i, w in enumerate(war_list[:years])]

def estimate_price_per_win(tbl):
    """
    What did teams actually pay per projected win? For each winter: total dollars paid / projected wins (with the
    yearly price growth built in). The price used is the dollar-weighted average of the last three winters.
    """
    out = {}
    if tbl is None or len(tbl) == 0:
        return out
    for kind, g in tbl.groupby("kind"):
        g = g[g["wsum"] > 0.5]
        if len(g) < 15:
            continue
        by = g.groupby("walk_year").agg(deals=("total", "size"), paid=("total", "sum"), wins=("wsum", "sum"))
        by["price"] = by["paid"] / by["wins"]
        recent = sorted(by.index)[-3:]
        rg = g[g["walk_year"].isin(recent)]
        base = rg if len(rg) >= 15 else g
        price = float(base["total"].sum() / base["wsum"].sum())
        _price[kind] = price
        out[kind] = {"by_year": by, "price": price, "n": int(len(g)), "recent": recent}
    _price["table"] = out
    return out

def price_lines(res, years, kind, offer=None):
    """Price sensitivity: what the contract is worth if a win costs more or less, and what the offer implies."""
    base, g = price_per_win(kind), S.WAR_PRICE_INFLATION
    wsum = sum(max(w, 0) * (1 + g) ** i for i, w in enumerate(res["war"][:years]))
    parts = " | ".join(f"${base * m:,.1f}M per win: ${wsum * base * m:,.0f}M" for m in (0.75, 1.0, 1.25))
    lines = [f"If a win costs less or more: {parts}",
             f"(Price of a win used: ${base:,.1f}M, {price_source(kind)}.)"]
    if offer and wsum > 0:
        lines.append(f"Your offer works out to ${offer / wsum:,.1f}M per projected win.")
    return lines
