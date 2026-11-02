"""Charts (needs matplotlib)."""

import os
import re

from .config import CHART_DIR, S
from .util import fold


def _plt():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        print("  Charts need matplotlib. Install it with:  pip install matplotlib")
        return None

def _slug(name):
    return re.sub(r"[^a-z0-9]+", "_", fold(name)).strip("_") or "player"

def save_player_chart(name, kind, p, res):
    """Past WAR (dots) and projected WAR with its range (shaded band)."""
    plt = _plt()
    if plt is None:
        return None
    from matplotlib.ticker import MaxNLocator
    pct = int(round(S.RANGE_LEVEL * 100))
    hist = p[p["Season"] >= S.END_SEASON - 5].sort_values("Season")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(hist["Season"], hist["WAR"], "o-", color="#444444", label="Actual WAR")
    ax.plot(res["season"], res["war"], "o-", color="#1f77b4", label="Projected WAR")
    ax.fill_between(res["season"], res["war_low"], res["war_high"], color="#1f77b4", alpha=0.2, label=f"{pct}% range")
    ax.axhline(0, color="#999999", lw=0.8)
    ax.set_title(f"{name}: projected WAR, {res['season'][0]}-{res['season'][-1]}")
    ax.set_xlabel("Season (2020 is scaled to a 162-game pace)")
    ax.set_ylabel("WAR")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    os.makedirs(CHART_DIR, exist_ok=True)
    path = os.path.join(CHART_DIR, f"{_slug(name)}_projection.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path

def save_compare_chart(items, years):
    plt = _plt()
    if plt is None:
        return None
    from matplotlib.ticker import MaxNLocator
    pct = int(round(S.RANGE_LEVEL * 100))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for it, color in zip(items, ("#1f77b4", "#d62728")):
        res = it["res"]
        ax.plot(res["season"], res["war"], "o-", color=color, label=it["name"])
        ax.fill_between(res["season"], res["war_low"], res["war_high"], color=color, alpha=0.15)
    ax.axhline(0, color="#999999", lw=0.8)
    ax.set_title(f"Projected WAR, {years} years ({pct}% ranges shaded)")
    ax.set_xlabel("Season")
    ax.set_ylabel("WAR")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    os.makedirs(CHART_DIR, exist_ok=True)
    path = os.path.join(CHART_DIR, f"compare_{_slug(items[0]['name'])}_vs_{_slug(items[1]['name'])}.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path

def save_class_chart(out, path):
    """Free-agent class: total projected WAR with its range, best first."""
    plt = _plt()
    if plt is None:
        return None
    pct = int(round(S.RANGE_LEVEL * 100))
    d = out.sort_values("WAR_total", ascending=True).tail(25)
    fig, ax = plt.subplots(figsize=(8, max(4, 0.32 * len(d) + 1.5)))
    err = [d["WAR_total"] - d["WAR_low"], d["WAR_high"] - d["WAR_total"]]
    ax.barh(d["Name"] + " (" + d["Years"].astype(str) + " yr)", d["WAR_total"], xerr=err, color="#1f77b4",
            alpha=0.8, ecolor="#444444", capsize=2)
    ax.set_xlabel(f"Projected WAR over the contract ({pct}% range)")
    ax.set_title("Free-agent class: projected WAR")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
