"""Synthetic flight records for the dashboard (same schema can be filled from
real sources such as the EUROCONTROL Aviation Intelligence Portal datasets)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

AIRPORTS = {  # ICAO: (name, lat, lon, traffic weight)
    "EGLL": ("London Heathrow", 51.470, -0.454, 1.3),
    "LFPG": ("Paris CDG", 49.010, 2.548, 1.3),
    "EHAM": ("Amsterdam", 52.309, 4.764, 1.2),
    "EDDF": ("Frankfurt", 50.033, 8.570, 1.2),
    "LEMD": ("Madrid", 40.472, -3.561, 1.0),
    "LTFM": ("Istanbul", 41.262, 28.742, 1.3),
    "LIRF": ("Rome Fiumicino", 41.800, 12.239, 0.8),
    "EBBR": ("Brussels", 50.901, 4.484, 0.6),
    "LSZH": ("Zurich", 47.458, 8.555, 0.6),
    "LOWW": ("Vienna", 48.110, 16.570, 0.6),
}

# ATFM delay causes (simplified Network Manager regulation reason codes)
CAUSES = {"C": "ATC capacity", "S": "ATC staffing", "W": "Weather",
          "G": "Aerodrome capacity", "I": "Industrial action", "O": "Other"}

AIRCRAFT = ["A320", "B738", "A321", "E190", "AT76", "A333", "B77W", "A359"]
AIRCRAFT_P = [0.28, 0.24, 0.16, 0.10, 0.06, 0.06, 0.05, 0.05]
SEATS = {"A320": 180, "B738": 186, "A321": 220, "E190": 100, "AT76": 70,
         "A333": 290, "B77W": 380, "A359": 320}

COLUMNS = ["flight_id", "date", "adep", "ades", "aircraft_type", "seats",
           "distance_km", "atfm_delay_min", "atfm_cause", "taxi_out_min",
           "unimpeded_taxi_min", "arr_delay_min"]


def _dist_km(a: str, b: str) -> float:
    _, la1, lo1, _ = AIRPORTS[a]
    _, la2, lo2, _ = AIRPORTS[b]
    p1, p2 = np.radians(la1), np.radians(la2)
    dp, dl = p2 - p1, np.radians(lo2 - lo1)
    h = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return float(2 * 6371 * np.arcsin(np.sqrt(h)))


def generate(start: str = "2025-01-01", months: int = 12,
             flights_per_day: int = 160, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    codes = list(AIRPORTS)
    w = np.array([AIRPORTS[c][3] for c in codes])
    w = w / w.sum()
    unimpeded = {c: rng.uniform(8, 14) for c in codes}
    dates = pd.date_range(start, periods=months, freq="MS")
    days = pd.date_range(dates[0], dates[-1] + pd.offsets.MonthEnd(0), freq="D")

    frames = []
    for d in days:
        summer = d.month in (6, 7, 8)
        n = int(flights_per_day * (1.25 if summer else 1.0))
        adep = rng.choice(codes, n, p=w)
        ades = rng.choice(codes, n, p=w)
        clash = adep == ades
        nxt = {c: codes[(i + 1) % len(codes)] for i, c in enumerate(codes)}
        ades[clash] = [nxt[a] for a in adep[clash]]
        ac = rng.choice(AIRCRAFT, n, p=AIRCRAFT_P)

        # Probability of being regulated rises in summer and on Fridays.
        p_reg = 0.07 + (0.08 if summer else 0) + (0.03 if d.dayofweek == 4 else 0)
        regulated = rng.random(n) < p_reg
        cause_p = ([.38, .22, .25, .10, .02, .03] if summer
                   else [.35, .20, .17, .20, .03, .05])
        cause = np.where(regulated, rng.choice(list(CAUSES), n, p=cause_p), "")
        atfm = np.where(regulated, rng.gamma(1.6, 11, n), 0.0)

        unimp = np.array([unimpeded[a] for a in adep])
        taxi = unimp + rng.gamma(1.5, 2.2 if not summer else 3.0, n)
        arr = atfm + (taxi - unimp) + rng.normal(-2, 11, n)

        frames.append(pd.DataFrame({
            "date": d, "adep": adep, "ades": ades, "aircraft_type": ac,
            "atfm_delay_min": atfm.round(1), "atfm_cause": cause,
            "taxi_out_min": taxi.round(1), "unimpeded_taxi_min": unimp.round(1),
            "arr_delay_min": arr.round(1),
        }))
    df = pd.concat(frames, ignore_index=True)
    df["seats"] = df["aircraft_type"].map(SEATS)
    pairs = {(a, b): _dist_km(a, b) for a in codes for b in codes if a != b}
    df["distance_km"] = [round(pairs[(a, b)]) for a, b in zip(df["adep"], df["ades"])]
    df.insert(0, "flight_id", [f"X{i:07d}" for i in range(len(df))])
    return df[COLUMNS]


def load(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"], keep_default_na=False,
                     na_values={c: [""] for c in COLUMNS if c != "atfm_cause"})
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    return df
