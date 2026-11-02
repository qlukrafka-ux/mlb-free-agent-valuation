"""The interactive program, its prompts and command-line options."""

import os
import re
import sys
import numpy as np
import pandas as pd

from .config import BASE_DIR, DATA_DIR, KIND, POS_GROUPS, RUNS_PER_WIN, S, VALIDATION_DIR
from .util import norm_pos, parse_money, parse_years
from .data import clean, find_player, load_raw, suggest_names
from .aging import fit_models
from .projection import project
from .ranges import compute_error_bands
from .contracts import fit_contract_models
from .charts import save_player_chart
from .display import compare_players, show_player
from .validation import Tee, backtest, tune, validate
from .reports import export_projections, free_agent_report


def ask_offer(default=None):
    """Question 1: the total contract amount."""
    while True:
        if default:
            t = input(f"How much is the total contract? [{default:,.0f}] (Enter keeps it, 'skip' removes it): ").strip()
            if not t:
                return default
            if t.lower() in ("skip", "none", "-", "0"):
                return None
        else:
            t = input("How much is the total contract? (for example 150, $150M or $150,000,000; Enter to skip): ").strip()
            if not t:
                return None
        v = parse_money(t)
        if v and v > 0:
            print(f"  Got it: ${v:,.1f}M total.")
            return v
        print("  Sorry, I couldn't read that amount. Try something like 150 or $150,000,000.")

def ask_years(default=None):
    """Question 2: the contract length."""
    default = default or S.DEFAULT_YEARS
    while True:
        t = input(f"How many years is the contract? [{default}]: ").strip()
        if not t:
            return default
        y = parse_years(t)
        if y:
            return y
        print("  Please enter a whole number of years between 1 and 15 (for example: 5).")

def ask_volume(kind, name, why, guess):
    unit = KIND[kind]["vol"]
    while True:
        t = input(f"{name} {why}, so his playing time is a guess. How many {unit} do you expect next season? "
                  f"(Enter = the model's estimate of about {guess:.0f}): ").strip()
        if not t:
            return None
        try:
            v = float(t.replace(",", ""))
            if 0 < v <= 1000:
                return v
        except ValueError:
            pass
        print(f"  Please enter a number of {unit}, for example {600 if kind == 'bat' else 180}.")

def ask_position(current):
    while True:
        t = input(f"Position group? Type C, SS, 2B, 3B, CF, LF, RF, 1B or DH (Enter keeps {current}): ").strip()
        if not t:
            return None
        g = norm_pos(t)
        if g:
            return g
        print("  I don't know that position. Use C, SS, 2B, 3B, CF, LF, RF, 1B or DH.")

def pick_player(data, query):
    hits = find_player(data, query)
    if not hits:
        print(f"  No player matching '{query}' with data in the last 2 seasons.")
        close = suggest_names(data, query)
        if close:
            print("  Did you mean: " + ", ".join(close) + "?")
        return None
    if len(hits) == 1:
        return hits[0]
    print(f"  {len(hits)} matches" + (" (showing 15)" if len(hits) > 15 else "") + ":")
    for i, h in enumerate(hits[:15]):
        print(f"  {i + 1}. {h[2]} ({KIND[h[0]]['label']}, last season {h[3]})")
    choice = input("  Pick a number (or Enter to search again): ").strip()
    if not choice.isdigit() or not 1 <= int(choice) <= min(len(hits), 15):
        return None
    return hits[int(choice) - 1]

def run_compare(data, models, contract_models, bands, q):
    rest = re.sub(r"^compare\s*", "", q, flags=re.I).strip()
    if re.search(r"\s+vs\.?\s+", rest, flags=re.I):
        first, second = re.split(r"\s+vs\.?\s+", rest, maxsplit=1, flags=re.I)
    else:
        first = rest or input("First player: ").strip()
        second = input("Second player: ").strip()
    h1 = pick_player(data, first) if first else None
    h2 = pick_player(data, second) if h1 and second else None
    if not (h1 and h2):
        return
    compare_players(data, models, contract_models, bands, h1, h2, ask_years())

def analyze_player(data, models, contract_models, bands, hit):
    kind, pid, name = hit[0], hit[1], hit[2]
    p = data[kind][data[kind]["IDfg"] == pid]
    probe = project(p, kind, models[kind], S.END_SEASON, 1)
    state = {"offer": None, "years": None, "vol1": None, "pos": None}
    print(f"\n{name}: {KIND[kind]['label']}" + (f", position group {probe['pos_group']}" if probe["pos_group"] else ""))
    if probe["limited"] or probe["injured"]:
        why = "has limited MLB history" if probe["limited"] else "missed time recently"
        state["vol1"] = ask_volume(kind, name, why, probe["vol"][0])
    ask = True
    while True:
        if ask:
            state["offer"] = ask_offer(state["offer"])
            state["years"] = ask_years(state["years"])
        res = show_player(data, models, contract_models, bands, kind, pid, state["years"],
                          state["offer"], state["vol1"], state["pos"])
        opts = "[Enter] new player   [c] different contract" + ("   [p] change position" if kind == "bat" else "")
        opts += "   [g] save chart   [x] compare with another player"
        action = None
        while action is None:
            choice = input(f"\nNext: {opts}\n> ").strip().lower()
            if choice == "":
                action = "new"
            elif choice == "c":
                action = "ask"
            elif choice == "p" and kind == "bat":
                new_pos = ask_position(res["pos_group"])
                if new_pos:
                    state["pos"] = new_pos
                    action = "redo"
            elif choice == "g":
                path = save_player_chart(name, kind, p, res)
                if path:
                    print(f"  Chart saved: {path}")
            elif choice == "x":
                other = input("  Compare with which player? ").strip()
                h2 = pick_player(data, other) if other else None
                if h2:
                    compare_players(data, models, contract_models, bands, hit, h2, state["years"])
            else:
                print("  Press Enter, or type c, p, g or x.")
        if action == "new":
            return
        ask = action == "ask"

def check_setup(data):
    print(f"\n{'=' * 70}\nSETUP CHECK\n{'=' * 70}")
    print(f"Python {sys.version.split()[0]}, pandas {pd.__version__}, numpy {np.__version__}")
    try:
        import pybaseball  # noqa: F401
        print("pybaseball: installed")
    except ImportError:
        print("pybaseball: NOT installed (run: pip install pybaseball)")
    print(f"Project folder: {BASE_DIR}")
    for kind in KIND:
        path = os.path.join(DATA_DIR, f"{S.SOURCE}_{kind}_{S.START_SEASON}_{S.END_SEASON}_v3.csv")
        print(f"  data file {'found  ' if os.path.exists(path) else 'MISSING'}: {path}")
    bat = data["bat"]
    print(f"Seasons loaded: {int(bat['Season'].min())}-{int(bat['Season'].max())}")
    if "r_bat" not in bat.columns:
        print("\nThe hitter component columns (runs_bat, runs_br, runs_field, runs_position) were NOT found, so the "
              "total-WAR model is being used.\nDelete the files in the data folder and rerun to download them again.")
        return
    err = float((bat[["r_bat", "r_run", "r_fld", "r_pos", "r_rest"]].sum(axis=1) - bat["rate"]).abs().max())
    print(f"Hitter components: found. Parts add back to total WAR (largest difference {err:.6f}).")
    print("\nPosition groups (inferred from each hitter's positional adjustment), last 3 seasons:")
    rows = []
    for grp in POS_GROUPS:
        sub = bat[(bat["Season"] > S.END_SEASON - 3) & (bat["pgrp"] == grp)]
        top = bat[(bat["Season"] == S.END_SEASON) & (bat["pgrp"] == grp)].nlargest(4, "WAR")["Name"].tolist()
        rows.append({"Group": grp, "Players": int(sub["IDfg"].nunique()),
                     "Avg position runs per 600 PA": round(float((sub["r_pos"] * RUNS_PER_WIN).mean()), 1) if len(sub) else np.nan,
                     f"Top {S.END_SEASON} WAR in group": ", ".join(top)})
    print(pd.DataFrame(rows).to_string(index=False))
    print("\nCheck that the names look like the right positions (SS group = shortstops, etc.).")
    print("If many are wrong, adjust POS_CUTS near the top of the file, or give a player pos=SS when you query him.")
    print("\nAverage WAR per 600 PA by part, by group (last 3 seasons):")
    recent = bat[bat["Season"] > S.END_SEASON - 3]
    print(recent.groupby("pgrp")[["r_bat", "r_run", "r_fld", "r_pos", "r_rest", "rate"]].mean().round(2)
          .rename(columns={"r_bat": "batting", "r_run": "baserun", "r_fld": "fielding", "r_pos": "position",
                           "r_rest": "repl/other", "rate": "total"}).to_string())

WELCOME = """
==================== MLB WAR + CONTRACT CALCULATOR ====================
  1. Type a player's name (part of a name works, e.g. "judge").
  2. Answer two questions: the total contract, and how many years.
     (Money can be typed any way you like: 150, $150M, $150,000,000.)
  3. You get projected WAR with a range, what the contract is worth,
     and how your offer compares. Then charts, a position change, or a
     comparison with another player are one keystroke away.
  Type compare to put two players side by side, help for tips, q to quit.
========================================================================
"""

HELP = """
TIPS
  Player      Part of a name works ("judge"). If several match, pick a number.
  Two questions  The total contract (press Enter to skip it) and the number of years.
  Compare     Type "compare" or "judge vs soto". Both players are projected for the same number of years.
  After the results:  Enter = new player,  c = different contract,  p = change a hitter's position
              (shortstops and catchers get more position credit than corner outfielders, 1B and DH),
              g = save a chart,  x = compare with another player.
  Playing time  For call-ups and players who missed time you'll be asked how many PA or IP to expect.
  Settings    Open settings.toml to change the price of a win, range width, seasons, and more.
"""

USAGE = """Usage: python war_model.py [option]
  (no option)            interactive calculator (type compare for two players side by side)
  --check                check your setup and the data (position groups, columns); run this first if anything looks off
  --backtest             WAR projection accuracy test only
  --validate             full validation: data checks, WAR backtest, contract out-of-time test
                         (also saved to validation/validation_report.txt)
  --tune                 try other recency weights / regression amounts (picked early, confirmed late)
  --freeagents [file]    project a list of free agents (default file: free_agents.csv);
                         saves reports/free_agent_class_report.csv and .md
  --help                 show this message
"""

def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(USAGE)
        return
    tee = None
    if "--validate" in args:
        os.makedirs(VALIDATION_DIR, exist_ok=True)
        report_path = os.path.join(VALIDATION_DIR, "validation_report.txt")
        tee = Tee(report_path)
        sys.stdout = tee
    try:
        from .config import SETTINGS_NOTES
        for note in SETTINGS_NOTES:
            print(f"Note: {note}")
        if S.SETTINGS_FILE:
            print(f"Settings: {S.SETTINGS_FILE}")
        data = {k: clean(load_raw(k), k) for k in KIND}
        if S.HITTER_MODEL == "components" and "r_bat" not in data["bat"].columns:
            print("Note: the hitter component columns are missing from the data, so the total-WAR model is used. "
                  "Run --check for details.")
        if "--check" in args:
            check_setup(data)
            return
        models = {k: fit_models(data[k], k, S.END_SEASON) for k in KIND}

        print("\nAging curve (expected change in WAR per full season, by age):")
        for kind, cfg in KIND.items():
            pts = ", ".join(f"{a}->{a + 1}: {models[kind]['rate'](a):+.2f}" for a in (24, 27, 30, 33, 36))
            print(f"  {cfg['label']}s (per {cfg['rate_base']} {cfg['vol']}): {pts}")

        print("\nContract data:")
        contract_models = fit_contract_models(data)

        if "--backtest" in args:
            backtest(data)
            return
        if "--validate" in args:
            validate(data)
            return
        if "--tune" in args:
            tune(data)
            return

        print("\nCalibrating uncertainty ranges from the backtest (a few seconds)...")
        bands = compute_error_bands(data)

        if "--freeagents" in args:
            i = args.index("--freeagents")
            file_arg = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith("--") else None
            free_agent_report(data, models, contract_models, bands, file_arg)
            return

        for kind in KIND:
            export_projections(data, models[kind], kind)

        print(WELCOME)
        try:
            while True:
                q = input("Player name (help, compare, q to quit): ").strip()
                ql = q.lower()
                if ql in ("q", "quit", "exit"):
                    break
                if not q:
                    continue
                if ql in ("help", "?"):
                    print(HELP)
                    continue
                if ql.startswith("compare") or re.search(r"\s+vs\.?\s+", ql):
                    run_compare(data, models, contract_models, bands, q)
                    continue
                hit = pick_player(data, q)
                if hit:
                    analyze_player(data, models, contract_models, bands, hit)
        except (EOFError, KeyboardInterrupt):
            pass
        print("Goodbye!")
    finally:
        if tee:
            sys.stdout = tee.screen
            tee.close()
            print(f"Report saved to {report_path}")
