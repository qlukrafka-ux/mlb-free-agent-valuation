"""
Settings and constants.

Everything you are likely to want to change lives in settings.toml (next to war_model.py).
This file holds the defaults and the fixed tables, and loads settings.toml on import.
"""
import os
from types import SimpleNamespace

# ---- folders (the project folder is one level above this package) ----
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")                # downloaded WAR data
REPORT_DIR = os.path.join(BASE_DIR, "reports")           # free-agent class reports
VALIDATION_DIR = os.path.join(BASE_DIR, "validation")    # validation report and backtest files
CHART_DIR = os.path.join(BASE_DIR, "charts")             # saved charts
CONTRACT_FILE = "contracts.csv"

# ---- settings (defaults; settings.toml overrides them) ----
S = SimpleNamespace(
    SOURCE="bref",               # "bref" (Baseball-Reference WAR) or "fangraphs" (blocked on many cloud IPs)
    START_SEASON=2015,
    END_SEASON=2026,             # last completed season in the data
    PRICE_PER_WIN="auto",        # "auto": measure the price of a win from contracts.csv, or a number ($ millions)
    DOLLARS_PER_WAR=8.0,         # fallback $ millions per WAR when it can't be measured (a placeholder)
    WAR_PRICE_INFLATION=0.05,    # yearly growth in the price of a win
    DEFAULT_YEARS=5,
    YEARS_BY_AGE=[(28, 7), (30, 6), (32, 4), (34, 3)],   # free-agent report: (max age, years); older gets 2
    SEASON_WEIGHTS=[5, 4, 3],    # most recent season first
    HITTER_MODEL="components",   # "components" or "total"
    DROPOUT_WEIGHT=0.0,          # survivor-bias fix weight (0 = off; 0.5 was tested and did not help, see README)
    REPLACEMENT_RATE=0.5,        # WAR per 600 PA (or 180 IP) at or below this counts as replacement level
    RANGE_LEVEL=0.68,            # share of outcomes the displayed range should cover
    USE_SPECIAL_CASES=True,      # rookie / missed-time handling
    RETURN_FACTOR=0.90,
    FULL_SEASON_GAMES=145,
    STARTS_PER_SEASON=28,
    RELIEF_APPEARANCES=60,
    ROLE_MIN_PA_PER_G=3.4,
    SETTINGS_FILE=None,
)

KIND = {
    "bat": dict(label="Hitter", vol="PA", rate_base=600, qual=50, min_vol=150,
                bt_min=200, reg=1200, vol_cap=720, extra="wRC+",
                heal_min=400, rookie_vol=1000),
    "pit": dict(label="Pitcher", vol="IP", rate_base=180, qual=20, min_vol=40,
                bt_min=50, reg=500, vol_cap=230, extra="FIP",
                heal_min=70, rookie_vol=260),
}

# Hitter WAR is split into parts that are projected separately (see README).
RUNS_PER_WIN = 10.0
COMPONENTS = {
    # name: column, regression amount (PA of average-for-his-position play blended in), aging depends on position class?
    "bat":  dict(col="r_bat",  reg=1200, by_class=False, label="batting"),
    "run":  dict(col="r_run",  reg=1800, by_class=False, label="baserunning"),
    "fld":  dict(col="r_fld",  reg=2400, by_class=True,  label="fielding"),
    "pos":  dict(col="r_pos",  reg=0,    by_class=True,  label="position"),
    "rest": dict(col="r_rest", reg=600,  by_class=False, label="replacement/other"),
}
POS_GROUPS = ["C", "SS", "2B/3B/CF", "LF/RF", "1B", "DH"]
POS_CLASS = {"C": "premium", "SS": "premium", "2B/3B/CF": "middle", "LF/RF": "corner", "1B": "corner", "DH": "corner"}
# Position group is inferred from the positional-adjustment runs per 600 PA (highest first); below the last cut = DH.
POS_CUTS = [(4.5, "SS"), (-2.0, "2B/3B/CF"), (-8.0, "LF/RF"), (-12.0, "1B")]     # below the last cut = DH
POS_DEFAULT_RUNS = {"C": 9.5, "SS": 6.0, "2B/3B/CF": 2.2, "LF/RF": -6.0, "1B": -10.0, "DH": -14.0}   # fallback only
POS_ALIASES = {"c": "C", "catcher": "C", "ss": "SS", "shortstop": "SS", "2b": "2B/3B/CF", "3b": "2B/3B/CF",
               "cf": "2B/3B/CF", "2b/3b/cf": "2B/3B/CF", "mid": "2B/3B/CF", "lf": "LF/RF", "rf": "LF/RF",
               "of": "LF/RF", "lf/rf": "LF/RF", "corner": "LF/RF", "1b": "1B", "dh": "DH"}

# The 155 free-agent deals used if you have no contracts.csv yet.
DEFAULT_CONTRACTS = """Name,kind,walk_year,years,total_value_m
Anthony Rendon,bat,2019,7,245
Josh Donaldson,bat,2019,4,92
Gerrit Cole,pit,2019,9,324
Stephen Strasburg,pit,2019,7,245
Zack Wheeler,pit,2019,5,118
Madison Bumgarner,pit,2019,5,85
Drew Pomeranz,pit,2019,4,34
George Springer,bat,2020,6,150
J.T. Realmuto,bat,2020,5,115.5
DJ LeMahieu,bat,2020,6,90
Marcell Ozuna,bat,2020,4,65
Didi Gregorius,bat,2020,2,28
Michael Brantley,bat,2020,2,32
Kolten Wong,bat,2020,2,18
James McCann,bat,2020,4,40
Andrelton Simmons,bat,2020,1,10.5
Nelson Cruz,bat,2020,1,13
Marcus Semien,bat,2020,1,18
Trevor Bauer,pit,2020,3,102
Liam Hendriks,pit,2020,3,54
Freddie Freeman,bat,2021,6,162
Marcus Semien,bat,2021,7,175
Corey Seager,bat,2021,10,325
Trevor Story,bat,2021,6,140
Kris Bryant,bat,2021,7,182
Nick Castellanos,bat,2021,5,100
Kyle Schwarber,bat,2021,4,79
Starling Marte,bat,2021,4,78
Jorge Soler,bat,2021,3,36
Yan Gomes,bat,2021,2,13
Kevin Gausman,pit,2021,5,110
Marcus Stroman,pit,2021,3,71
Aaron Judge,bat,2022,9,360
Trea Turner,bat,2022,11,300
Xander Bogaerts,bat,2022,11,280
Carlos Correa,bat,2022,6,200
Dansby Swanson,bat,2022,7,177
Brandon Nimmo,bat,2022,8,162
Willson Contreras,bat,2022,5,87.5
Jose Abreu,bat,2022,3,58.5
Anthony Rizzo,bat,2022,2,40
Justin Turner,bat,2022,2,21.7
Andrew Benintendi,bat,2022,5,75
Josh Bell,bat,2022,2,33
Trey Mancini,bat,2022,2,14
Brandon Drury,bat,2022,2,17
Jean Segura,bat,2022,2,17
Christian Vazquez,bat,2022,3,30
Jacob deGrom,pit,2022,5,185
Carlos Rodon,pit,2022,6,162
Justin Verlander,pit,2022,2,86.7
Jameson Taillon,pit,2022,4,68
Chris Bassitt,pit,2022,3,63
Kenley Jansen,pit,2022,2,32
Edwin Diaz,pit,2022,5,102
Rafael Montero,pit,2022,3,34.5
Tyler Anderson,pit,2022,3,39
Jordan Lyles,pit,2022,2,17
Adam Ottavino,pit,2022,2,14.5
Robert Suarez,pit,2022,5,46
Drew Smyly,pit,2022,2,19
Cody Bellinger,bat,2023,3,80
Matt Chapman,bat,2023,3,54
Jeimer Candelario,bat,2023,3,45
Jorge Soler,bat,2023,3,42
Lourdes Gurriel Jr.,bat,2023,3,42
Rhys Hoskins,bat,2023,2,34
Aaron Nola,pit,2023,7,172
Josh Hader,pit,2023,5,95
Eduardo Rodriguez,pit,2023,4,80
Sonny Gray,pit,2023,3,75
Blake Snell,pit,2023,2,62
Seth Lugo,pit,2023,3,45
Jordan Hicks,pit,2023,4,44
Lucas Giolito,pit,2023,2,38.5
Marcus Stroman,pit,2023,2,37
Robert Stephenson,pit,2023,3,33
Michael Wacha,pit,2023,2,32
Reynaldo Lopez,pit,2023,3,30
Sean Manaea,pit,2023,2,28
Nick Martinez,pit,2023,2,26
Jordan Montgomery,pit,2023,1,25
Juan Soto,bat,2024,15,765
Willy Adames,bat,2024,7,182
Tyler O'Neill,bat,2024,3,49.5
Michael Conforto,bat,2024,1,17
Gary Sanchez,bat,2024,1,8.5
Danny Jansen,bat,2024,1,8.5
Kyle Higashioka,bat,2024,2,13.5
Thairo Estrada,bat,2024,1,3.25
Mike Tauchman,bat,2024,1,1.95
Max Fried,pit,2024,8,218
Blake Snell,pit,2024,5,182
Nathan Eovaldi,pit,2024,3,75
Luis Severino,pit,2024,3,67
Yusei Kikuchi,pit,2024,3,63.675
Clay Holmes,pit,2024,3,38
Frankie Montas,pit,2024,2,34
Matt Boyd,pit,2024,2,29
Shane Bieber,pit,2024,2,26
Blake Treinen,pit,2024,2,22
Yimi Garcia,pit,2024,2,15
Alex Cobb,pit,2024,1,15
Aroldis Chapman,pit,2024,1,10.75
Jordan Romano,pit,2024,1,8.5
Kyle Tucker,bat,2025,4,240
Alex Bregman,bat,2025,5,175
Bo Bichette,bat,2025,3,126
Pete Alonso,bat,2025,5,155
Cody Bellinger,bat,2025,5,162.5
Kyle Schwarber,bat,2025,5,150
Josh Naylor,bat,2025,5,92.5
J.T. Realmuto,bat,2025,3,45
Eugenio Suarez,bat,2025,1,15
Jorge Polanco,bat,2025,2,40
Ha-Seong Kim,bat,2025,1,20
Ryan O'Hearn,bat,2025,2,29
Harrison Bader,bat,2025,2,20.5
Luis Arraez,bat,2025,1,12
Marcell Ozuna,bat,2025,1,12
Mike Yastrzemski,bat,2025,2,23
Victor Caratini,bat,2025,2,14
Cedric Mullins,bat,2025,1,7
Adolis Garcia,bat,2025,1,10
Willi Castro,bat,2025,2,12.8
Danny Jansen,bat,2025,2,14.5
Paul Goldschmidt,bat,2025,1,4
Lane Thomas,bat,2025,1,5.25
Dylan Cease,pit,2025,7,210
Framber Valdez,pit,2025,3,115
Ranger Suarez,pit,2025,5,130
Michael King,pit,2025,3,75
Merrill Kelly,pit,2025,2,40
Chris Bassitt,pit,2025,1,18.5
Justin Verlander,pit,2025,1,13
Adrian Houser,pit,2025,2,22
Steven Matz,pit,2025,2,15
Tyler Mahle,pit,2025,1,10
Zach Eflin,pit,2025,1,10
Nick Martinez,pit,2025,1,13
Jose Quintana,pit,2025,1,6
Edwin Diaz,pit,2025,3,69
Devin Williams,pit,2025,3,51
Robert Suarez,pit,2025,3,45
Ryan Helsley,pit,2025,2,28
Tyler Rogers,pit,2025,3,37
Luke Weaver,pit,2025,2,22
Kyle Finnegan,pit,2025,2,19
Brad Keller,pit,2025,2,22
Phil Maton,pit,2025,2,14.5
Seranthony Dominguez,pit,2025,2,20
Emilio Pagan,pit,2025,2,20
Pete Fairbanks,pit,2025,1,13
Raisel Iglesias,pit,2025,1,16
Kenley Jansen,pit,2025,1,11
"""

# STARTER free-agent list, used if you have no free_agents.csv yet. Confirm it against MLB Trade Rumors.
DEFAULT_FREE_AGENTS = [
    # name, kind, note. STARTER LIST built from preseason / in-season previews. Confirm against MLB Trade Rumors'
    # official list after the World Series: options, opt-outs and extensions decide who actually reaches the market.
    ("Tarik Skubal", "pit", "Top of the class in every preview; had elbow surgery in 2026, check status"),
    ("Randy Arozarena", "bat", ""), ("Seiya Suzuki", "bat", ""), ("Casey Mize", "pit", ""),
    ("Jazz Chisholm Jr.", "bat", ""), ("Nico Hoerner", "bat", ""),
    ("Brandon Woodruff", "pit", "Injury history; confirm option status"),
    ("Eugenio Suarez", "bat", ""), ("Luis Arraez", "bat", ""), ("Ha-Seong Kim", "bat", ""),
    ("Alec Bohm", "bat", ""), ("Ryan Mountcastle", "bat", ""), ("Tyler Stephenson", "bat", ""),
    ("Ryan Jeffers", "bat", ""), ("J.P. Crawford", "bat", ""), ("Taylor Ward", "bat", ""),
    ("Ramon Laureano", "bat", ""), ("Lane Thomas", "bat", ""), ("Brandon Lowe", "bat", ""),
    ("Jonathan India", "bat", ""), ("Gleyber Torres", "bat", ""), ("Trevor Rogers", "pit", ""),
    ("Sonny Gray", "pit", "Club/mutual option, may not reach the market"),
    ("Michael King", "pit", "Can opt out of his contract, may not reach the market"),
    ("Bo Bichette", "bat", "Can opt out of his contract, may not reach the market"),
]


# ============================ settings.toml ============================
_MAP = {   # (section, key): setting name
    ("data", "source"): "SOURCE", ("data", "start_season"): "START_SEASON", ("data", "end_season"): "END_SEASON",
    ("price", "price_per_win"): "PRICE_PER_WIN", ("price", "fallback_dollars_per_win"): "DOLLARS_PER_WAR",
    ("price", "yearly_price_growth"): "WAR_PRICE_INFLATION",
    ("ranges", "range_level"): "RANGE_LEVEL",
    ("model", "hitter_model"): "HITTER_MODEL", ("model", "season_weights"): "SEASON_WEIGHTS",
    ("model", "survivor_bias_weight"): "DROPOUT_WEIGHT", ("model", "replacement_rate"): "REPLACEMENT_RATE",
    ("special_cases", "use_special_cases"): "USE_SPECIAL_CASES", ("special_cases", "return_factor"): "RETURN_FACTOR",
    ("special_cases", "full_season_games"): "FULL_SEASON_GAMES",
    ("special_cases", "starts_per_season"): "STARTS_PER_SEASON",
    ("special_cases", "relief_appearances"): "RELIEF_APPEARANCES",
    ("special_cases", "min_pa_per_game_for_starter"): "ROLE_MIN_PA_PER_G",
    ("contracts", "default_years"): "DEFAULT_YEARS", ("contracts", "years_by_age"): "YEARS_BY_AGE",
}
_REGS = {"batting": ("comp", "bat"), "baserunning": ("comp", "run"), "fielding": ("comp", "fld"),
         "position": ("comp", "pos"), "replacement_other": ("comp", "rest"),
         "hitter_total_rate": ("kind", "bat"), "pitcher_total_rate": ("kind", "pit")}


def load_settings():
    """Read settings.toml (next to war_model.py, or in the folder you ran Python from). Returns a list of notes."""
    notes = []
    path = next((p for p in (os.path.join(BASE_DIR, "settings.toml"), os.path.join(os.getcwd(), "settings.toml"))
                 if os.path.exists(p)), None)
    if path is None:
        return notes
    try:
        import tomllib
    except ImportError:
        return ["settings.toml needs Python 3.11 or newer to be read; using the built-in defaults."]
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:                                   # a typo in the file should not crash the program
        return [f"Couldn't read {path}: {e}. Using the built-in defaults."]
    S.SETTINGS_FILE = path
    for section, table in data.items():
        if not isinstance(table, dict):
            notes.append(f"settings.toml: ignored '{section}' (expected a [section]).")
            continue
        for key, value in table.items():
            if section == "regression" and key in _REGS:
                kind, name = _REGS[key]
                (COMPONENTS[name] if kind == "comp" else KIND[name])["reg"] = value
            elif section == "positions" and key == "cuts":
                POS_CUTS[:] = [(float(c), str(g)) for c, g in value]
            elif (section, key) in _MAP:
                name = _MAP[(section, key)]
                if name == "YEARS_BY_AGE":
                    value = [(int(a), int(b)) for a, b in value]
                setattr(S, name, value)
            else:
                notes.append(f"settings.toml: unknown setting [{section}] {key} (ignored).")
    if not 0 <= float(S.RANGE_LEVEL) < 1:
        notes.append("settings.toml: range_level must be between 0 and 0.99; using 0.68.")
        S.RANGE_LEVEL = 0.68
    if S.HITTER_MODEL not in ("components", "total"):
        notes.append("settings.toml: hitter_model must be \"components\" or \"total\"; using components.")
        S.HITTER_MODEL = "components"
    return notes


SETTINGS_NOTES = load_settings()
