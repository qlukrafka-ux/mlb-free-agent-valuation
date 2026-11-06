"""
Basic tests. Run from the project folder with:  pip install pytest  &&  pytest
They use small made-up data, so they need no internet and no pybaseball download.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mlbwar as wm  # noqa: E402
import mlbwar.config as cfg  # noqa: E402
import mlbwar.charts as charts  # noqa: E402


# ----------------------------- helpers -----------------------------
def make_hitters(n=250, seed=0):
    """A small made-up league: raw rows in the layout clean() expects."""
    rng = np.random.default_rng(seed)
    rows = []
    for pid in range(1, n + 1):
        talent = rng.normal(2.0, 1.2)
        debut_age = int(rng.integers(21, 27))
        start = int(rng.integers(2015, 2022))
        for season in range(start, min(start + int(rng.integers(3, 10)), wm.S.END_SEASON + 1)):
            age = debut_age + (season - start)
            pa = int(np.clip(rng.normal(500, 120), 120, 700))
            war = (talent + rng.normal(0, 0.8)) * pa / 600
            rows.append({"IDfg": pid, "Name": f"Player {pid}", "Season": season, "Age": age,
                         "WAR": war, "PA": pa, "G": int(pa / 4.1), "wRC+": 100})
    return pd.DataFrame(rows)


def one_player(rows):
    """rows = [(season, age, pa, g, war), ...] -> cleaned frame for a single player."""
    raw = pd.DataFrame([{"IDfg": 999999, "Name": "Test Player", "Season": s, "Age": a, "WAR": w, "PA": pa,
                         "G": g, "wRC+": 110} for s, a, pa, g, w in rows])
    return wm.clean(raw, "bat")


def league():
    df = wm.clean(make_hitters(), "bat")
    return df, wm.fit_models(df, "bat", wm.S.END_SEASON)


# ----------------------------- input parsing -----------------------------
def test_parse_money_accepts_many_formats():
    assert wm.parse_money("150") == 150
    assert wm.parse_money("$150M") == 150
    assert wm.parse_money("150 million") == 150
    assert wm.parse_money("$150,000,000") == 150
    assert abs(wm.parse_money("1.2b") - 1200) < 1e-9
    assert wm.parse_money("abc") is None
    assert wm.parse_money("") is None


def test_parse_years_and_kind():
    assert wm.parse_years("5 years") == 5
    assert wm.parse_years("5yrs") == 5
    assert wm.parse_years("0") is None
    assert wm.parse_years("40") is None
    assert wm.norm_kind("Hitter") == "bat"
    assert wm.norm_kind("pitcher") == "pit"
    assert wm.norm_kind("x") is None


def test_name_folding_ignores_accents_and_suffixes():
    assert wm.fold("José Abreu") == wm.fold("Jose Abreu")
    assert wm.fold("Lourdes Gurriel Jr.") == wm.fold("Lourdes Gurriel")
    assert wm.fold("J.T. Realmuto") == wm.fold("JT Realmuto")


# ----------------------------- contract math -----------------------------
def test_market_value_inflates_and_never_goes_negative():
    vals = wm.market_value([2.0, 2.0], 2, dollars_per_war=10, inflation=0.10)
    assert vals == [20.0, 22.0]
    assert wm.market_value([-1.0], 1, dollars_per_war=10, inflation=0.0) == [0.0]


def test_verdict_thresholds():
    assert "BARGAIN" in wm.verdict(80, 100)
    assert "OVERPAY" in wm.verdict(120, 100)
    assert "FAIR" in wm.verdict(100, 100)


# ----------------------------- projection -----------------------------
def test_projection_is_rate_times_playing_time():
    df, models = league()
    pid = df.loc[df["Season"] == wm.S.END_SEASON, "IDfg"].iloc[0]
    res = wm.project(df[df["IDfg"] == pid], "bat", models, wm.S.END_SEASON, 3)
    assert len(res["war"]) == 3
    for war, rate, vol in zip(res["war"], res["rate"], res["vol"]):
        assert abs(war - rate * vol / wm.KIND["bat"]["rate_base"]) < 1e-9


def test_rookie_regular_gets_role_based_playing_time():
    # 60 games, 250 PA (4.2 PA per game), first season: an everyday player who was called up midyear
    df, models = league()
    rookie = one_player([(wm.S.END_SEASON, 23, 250, 60, 1.4)])
    both = pd.concat([df, rookie])
    with_fix = wm.project(rookie, "bat", models, wm.S.END_SEASON, 1, special=True)
    without = wm.project(rookie, "bat", models, wm.S.END_SEASON, 1, special=False)
    assert with_fix["limited"] is True
    assert with_fix["vol"][0] > 550            # about 4.2 x 145 games
    assert without["vol"][0] < 400             # the old formula gives roughly 0.5 x 250 + 200
    assert both["IDfg"].nunique() == df["IDfg"].nunique() + 1


def test_part_time_rookie_is_not_boosted():
    df, models = league()
    bench = one_player([(wm.S.END_SEASON, 24, 120, 60, 0.3)])   # 2 PA per game
    res = wm.project(bench, "bat", models, wm.S.END_SEASON, 1)
    assert res["vol"][0] < 400


def test_missed_season_uses_healthy_playing_time():
    df, models = league()
    vet = one_player([(wm.S.END_SEASON - 2, 29, 640, 156, 4.3), (wm.S.END_SEASON - 1, 30, 620, 150, 4.1),
                      (wm.S.END_SEASON, 31, 130, 32, 0.9)])
    with_fix = wm.project(vet, "bat", models, wm.S.END_SEASON, 1, special=True)
    without = wm.project(vet, "bat", models, wm.S.END_SEASON, 1, special=False)
    assert with_fix["injured"] is True
    assert with_fix["vol"][0] > without["vol"][0]
    assert with_fix["vol"][0] <= wm.KIND["bat"]["vol_cap"]


def test_user_playing_time_override():
    df, models = league()
    pid = df.loc[df["Season"] == wm.S.END_SEASON, "IDfg"].iloc[0]
    res = wm.project(df[df["IDfg"] == pid], "bat", models, wm.S.END_SEASON, 1, vol1=610)
    assert abs(res["vol"][0] - 610) < 1e-9


# ----------------------------- uncertainty ranges -----------------------------
def test_war_range_contains_projection_and_widens_with_horizon():
    bands = {"bat": {"tier_q": {i: (-1.5, 1.5) for i in range(4)}, "mult": {1: 1.0, 2: 1.2, 3: 1.4},
                     "flag_mult": {"limited": 1.3, "injured": 1.2}, "n": 100}}
    lo1, hi1 = wm.war_range(bands, "bat", 1, 3.0)
    lo3, hi3 = wm.war_range(bands, "bat", 3, 3.0)
    lo5, hi5 = wm.war_range(bands, "bat", 5, 3.0)
    assert lo1 <= 3.0 <= hi1
    assert (hi3 - lo3) > (hi1 - lo1)
    assert (hi5 - lo5) > (hi3 - lo3)
    lo_r, hi_r = wm.war_range(bands, "bat", 1, 3.0, limited=True)
    assert (hi_r - lo_r) > (hi1 - lo1)


def test_default_contract_years_shrink_with_age():
    assert wm.default_contract_years(26) > wm.default_contract_years(33) > wm.default_contract_years(40) - 1


def test_total_range_is_between_independent_and_fully_correlated():
    wars, lows, highs = [3.0, 3.0, 3.0], [1.5, 1.5, 1.5], [4.5, 4.5, 4.5]
    base = {"tier_q": {}, "mult": {1: 1.0}, "flag_mult": {}, "n": 1}
    lo0, hi0 = wm.total_range({"bat": dict(base, rho=0.0)}, "bat", wars, lows, highs)
    lo1, hi1 = wm.total_range({"bat": dict(base, rho=1.0)}, "bat", wars, lows, highs)
    lo5, hi5 = wm.total_range({"bat": dict(base, rho=0.5)}, "bat", wars, lows, highs)
    assert abs(lo1 - sum(lows)) < 1e-9 and abs(hi1 - sum(highs)) < 1e-9      # fully correlated = ranges add up
    assert (hi0 - lo0) < (hi5 - lo5) < (hi1 - lo1)                          # unrelated misses = tighter total
    assert lo0 <= sum(wars) <= hi0


def test_contract_value_range_brackets_the_value():
    res = {"war": [3.0, 3.0], "war_low": [1.0, 1.0], "war_high": [5.0, 5.0], "total_low": 3.0, "total_high": 9.0}
    v, lo, hi = wm.contract_value_range(res, 2)
    assert lo < v < hi


# ----------------------------- positions and components -----------------------------
POSR = {"C": 9.5, "SS": 6.0, "MID": 2.2, "COR": -6.0, "1B": -10.0, "DH": -14.0}


def make_hitters_with_parts(n=240, seed=3):
    """Made-up hitters whose WAR is built from batting / baserunning / fielding / position parts, like bWAR."""
    rng = np.random.default_rng(seed)
    groups = list(POSR)
    rows = []
    for pid in range(1, n + 1):
        grp = groups[pid % 6]
        talent = rng.normal(0, 5)
        debut_age = int(rng.integers(21, 27))
        start = int(rng.integers(2015, 2022))
        for season in range(start, min(start + int(rng.integers(3, 10)), wm.S.END_SEASON + 1)):
            pa = int(np.clip(rng.normal(500, 120), 150, 700))
            f = pa / 600
            bat, br = (talent + rng.normal(0, 6)) * f, rng.normal(0, 2) * f
            fld, pos = rng.normal(0, 5) * f, POSR[grp] * f
            war = (bat + br + fld + pos + 20 * f) / 10
            rows.append({"IDfg": pid, "Name": f"Player {pid}", "Season": season, "Age": debut_age + season - start,
                         "WAR": war, "PA": pa, "G": int(pa / 4.1), "wRC+": 100, "runs_bat": bat, "runs_run": br,
                         "runs_fld": fld, "runs_pos": pos, "runs_cat": 1.0 if grp == "C" else 0.0})
    return pd.DataFrame(rows)


def parts_league():
    df = wm.clean(make_hitters_with_parts(), "bat")
    return df, wm.fit_models(df, "bat", wm.S.END_SEASON)


def test_position_group_cut_points():
    assert wm.position_group(6.5) == "SS"
    assert wm.position_group(2.0) == "2B/3B/CF"
    assert wm.position_group(-6.0) == "LF/RF"
    assert wm.position_group(-10.0) == "1B"
    assert wm.position_group(-15.0) == "DH"
    assert wm.position_group(9.5) == "C"
    assert wm.position_group(6.0, catcher_runs=2.0) == "C"
    assert wm.norm_pos("rf") == "LF/RF" and wm.norm_pos("Shortstop") == "SS" and wm.norm_pos("zz") is None


def test_components_add_back_to_total_war_rate():
    df, _ = parts_league()
    total = df[["r_bat", "r_run", "r_fld", "r_pos", "r_rest"]].sum(axis=1)
    assert float((total - df["rate"]).abs().max()) < 1e-9
    assert set(df["pgrp"].unique()) <= set(wm.POS_GROUPS)


def test_shortstop_gets_more_position_credit_than_a_right_fielder():
    df, models = parts_league()
    pid = df.loc[df["Season"] == wm.S.END_SEASON, "IDfg"].iloc[0]
    p = df[df["IDfg"] == pid]
    ss = wm.project(p, "bat", models, wm.S.END_SEASON, 1, pos="SS")
    rf = wm.project(p, "bat", models, wm.S.END_SEASON, 1, pos="LF/RF")
    assert ss["method"] == "components" and rf["method"] == "components"
    assert ss["comp"][0]["pos"] > rf["comp"][0]["pos"]
    assert ss["rate"][0] > rf["rate"][0]


def test_component_projection_adds_up_and_total_method_still_works():
    df, models = parts_league()
    pid = df.loc[df["Season"] == wm.S.END_SEASON, "IDfg"].iloc[0]
    p = df[df["IDfg"] == pid]
    res = wm.project(p, "bat", models, wm.S.END_SEASON, 3)
    for rate, comp in zip(res["rate"], res["comp"]):
        assert abs(rate - sum(comp.values())) < 1e-9
    old = wm.project(p, "bat", models, wm.S.END_SEASON, 3, method="total")
    assert old["method"] == "total" and len(old["war"]) == 3


# ----------------------------- price of a win, survivor-bias fix, settings, charts -----------------------------
def test_price_of_a_win_is_measured_from_contracts_and_can_be_overridden():
    tbl = pd.DataFrame({"kind": ["bat"] * 20, "walk_year": [2023] * 10 + [2024] * 10,
                        "total": [100.0] * 20, "wsum": [10.0] * 10 + [8.0] * 10})
    saved = wm.S.PRICE_PER_WIN
    try:
        wm.S.PRICE_PER_WIN = "auto"
        info = wm.estimate_price_per_win(tbl)
        assert abs(info["bat"]["price"] - 2000.0 / 180.0) < 1e-9
        assert abs(wm.price_per_win("bat") - 2000.0 / 180.0) < 1e-9
        wm.S.PRICE_PER_WIN = 9.0
        assert wm.price_per_win("bat") == 9.0
    finally:
        wm.S.PRICE_PER_WIN = saved
        wm.estimate_price_per_win(None)


def test_price_sensitivity_lines_mention_offer_price_per_win():
    res = {"war": [3.0, 3.0]}
    lines = wm.price_lines(res, 2, "bat", offer=60)
    assert len(lines) == 3 and "per projected win" in lines[-1]


def test_survivor_bias_fix_steepens_the_aging_curve():
    df, _ = parts_league()
    c = wm.KIND["bat"]
    off = wm.fit_curve(df, "rate", "diff", c, wm.S.END_SEASON, impute=True, dropout_weight=0)
    on = wm.fit_curve(df, "rate", "diff", c, wm.S.END_SEASON, impute=True, dropout_weight=0.5)
    assert on(33) < off(33)
    assert on(28) <= off(28) + 1e-9


def test_settings_file_overrides_defaults():
    import tempfile
    keep = (wm.S.RANGE_LEVEL, wm.S.SETTINGS_FILE, cfg.BASE_DIR, cfg.COMPONENTS["bat"]["reg"], list(cfg.POS_CUTS))
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "settings.toml"), "w") as f:
            f.write('[ranges]\nrange_level = 0.5\n[regression]\nbatting = 999\n[nonsense]\nfoo = 1\n[ranges2]\nx = 1\n')
        try:
            cfg.BASE_DIR = d
            notes = cfg.load_settings()
            assert wm.S.RANGE_LEVEL == 0.5 and cfg.COMPONENTS["bat"]["reg"] == 999
            assert any("ignored" in n or "unknown" in n for n in notes) or notes == []
        finally:
            wm.S.RANGE_LEVEL, wm.S.SETTINGS_FILE, cfg.BASE_DIR = keep[0], keep[1], keep[2]
            cfg.COMPONENTS["bat"]["reg"] = keep[3]
            cfg.POS_CUTS[:] = keep[4]


def test_projection_chart_is_saved():
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return
    import tempfile
    df, models = parts_league()
    pid = df.loc[df["Season"] == wm.S.END_SEASON, "IDfg"].iloc[0]
    p = df[df["IDfg"] == pid]
    res = wm.project_with_ranges(p, "bat", models, None, 4)
    keep = charts.CHART_DIR
    with tempfile.TemporaryDirectory() as d:
        charts.CHART_DIR = d
        try:
            path = wm.save_player_chart("Test Player", "bat", p, res)
            assert path and os.path.exists(path) and os.path.getsize(path) > 1000
        finally:
            charts.CHART_DIR = keep


def test_reg_zero_turns_off_regression_for_components_too():
    df, models = parts_league()
    pid = df.loc[df["Season"] == wm.S.END_SEASON, "IDfg"].iloc[0]
    p = df[df["IDfg"] == pid]
    base = wm.project(p, "bat", models, wm.S.END_SEASON, 1)
    raw = wm.project(p, "bat", models, wm.S.END_SEASON, 1, reg=0)
    assert base["method"] == raw["method"] == "components"
    assert abs(base["rate"][0] - raw["rate"][0]) > 1e-6
