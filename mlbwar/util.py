"""Small helpers: name matching, reading money and years, position names."""

import unicodedata

from .config import POS_ALIASES, POS_CUTS


def fold(name):
    """Name matching helper: ignores accents, capitals, periods and Jr./Sr. ('Jose Abreu' = 'José Abreu')."""
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = s.replace(".", "").replace("'", "").replace("\u2019", "").replace("-", " ")
    parts = s.split()
    while parts and parts[-1] in ("jr", "sr", "ii", "iii", "iv"):
        parts.pop()
    return " ".join(parts)

def parse_money(text):
    """
    Turns what a person types into $ millions. All of these work:
      150   $150   150m   150 million   $150,000,000   1.2b   1.2 billion
    Plain numbers of 10,000 or more are treated as whole dollars; smaller ones as millions.
    Returns None if it can't be read.
    """
    if text is None:
        return None
    t = str(text).strip().lower().replace("$", "").replace(",", "").replace(" ", "").replace("_", "")
    if t in ("", "nan", "none"):
        return None
    mult = None
    for suffix, m in (("billion", 1000.0), ("b", 1000.0), ("million", 1.0), ("mm", 1.0), ("m", 1.0),
                      ("thousand", 0.001), ("k", 0.001)):
        if t.endswith(suffix):
            t, mult = t[:-len(suffix)], m
            break
    try:
        val = float(t)
    except ValueError:
        return None
    if mult is not None:
        return val * mult
    return val / 1_000_000 if val >= 10_000 else val

def parse_years(text):
    """'5', '5 years', '5yrs' -> 5. Returns None if unreadable or outside 1-15."""
    t = str(text).strip().lower()
    for w in ("years", "year", "yrs", "yr", "y"):
        t = t.replace(w, "")
    try:
        v = int(float(t.strip()))
    except ValueError:
        return None
    return v if 1 <= v <= 15 else None

def norm_kind(text):
    """'bat', 'batter', 'hitter' -> 'bat'; 'pit', 'pitcher' -> 'pit'."""
    t = str(text).strip().lower()
    if t[:1] in ("b", "h"):
        return "bat"
    if t[:1] == "p":
        return "pit"
    return None

def norm_pos(text):
    return POS_ALIASES.get(str(text).strip().lower())

def position_group(pos_runs_per_600, catcher_runs=0.0):
    """Approximate position group from the positional adjustment (and catcher-defense runs, if any)."""
    x = float(pos_runs_per_600)
    if x >= 8.5 or (abs(float(catcher_runs)) > 0.05 and x >= 5.0):
        return "C"
    for cut, grp in POS_CUTS:
        if x >= cut:
            return grp
    return "DH"
