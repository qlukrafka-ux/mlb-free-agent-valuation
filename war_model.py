"""
MLB WAR projections and free-agent contract valuation.

Run:   python war_model.py            (interactive calculator)
       python war_model.py --help     (all options)

The code lives in the mlbwar/ folder; your settings are in settings.toml.
"""
from mlbwar.cli import main

if __name__ == "__main__":
    main()
