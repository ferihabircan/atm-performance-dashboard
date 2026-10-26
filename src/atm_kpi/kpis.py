"""ATM performance indicators and CO2 estimates.

KPI definitions follow the spirit of the EUROCONTROL Performance Review
reports (punctuality threshold 15 min, en-route/airport ATFM delay per flight,
additional taxi-out time). Fuel coefficients are indicative values for
illustration, not certified emission factors.
"""
from __future__ import annotations

import pandas as pd

CO2_PER_KG_FUEL = 3.16  # kg CO2 per kg jet fuel (ICAO)
PUNCTUALITY_THRESHOLD_MIN = 15

# type: (LTO fuel kg, cruise fuel kg per km, taxi fuel flow kg per min)
FUEL = {
    "A320": (820, 2.7, 11), "B738": (850, 2.8, 11), "A321": (950, 3.1, 12),
    "E190": (600, 2.1, 8), "AT76": (250, 1.0, 5), "A333": (2000, 6.2, 22),
    "B77W": (2600, 7.8, 28), "A359": (1800, 5.7, 20),
}


def add_emissions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    lto = df["aircraft_type"].map(lambda t: FUEL[t][0])
    per_km = df["aircraft_type"].map(lambda t: FUEL[t][1])
    taxi_ff = df["aircraft_type"].map(lambda t: FUEL[t][2])
    df["add_taxi_min"] = (df["taxi_out_min"] - df["unimpeded_taxi_min"]).clip(lower=0)
    df["fuel_kg"] = lto + per_km * df["distance_km"] + taxi_ff * df["add_taxi_min"]
    df["co2_kg"] = df["fuel_kg"] * CO2_PER_KG_FUEL
    df["co2_add_taxi_kg"] = taxi_ff * df["add_taxi_min"] * CO2_PER_KG_FUEL
    return df


def summary(df: pd.DataFrame) -> dict:
    """Headline KPIs for any subset of flights."""
    n = len(df)
    if n == 0:
        return {k: 0.0 for k in ("flights", "punctuality_pct", "atfm_per_flight",
                                 "regulated_pct", "avg_delay_regulated",
                                 "add_taxi_min", "co2_t", "co2_g_per_seat_km")}
    df = df if "co2_kg" in df else add_emissions(df)
    reg = df["atfm_delay_min"] > 0
    return {
        "flights": n,
        "punctuality_pct": 100 * (df["arr_delay_min"] <= PUNCTUALITY_THRESHOLD_MIN).mean(),
        "atfm_per_flight": df["atfm_delay_min"].mean(),
        "regulated_pct": 100 * reg.mean(),
        "avg_delay_regulated": df.loc[reg, "atfm_delay_min"].mean() if reg.any() else 0.0,
        "add_taxi_min": df["add_taxi_min"].mean(),
        "co2_t": df["co2_kg"].sum() / 1000,
        "co2_g_per_seat_km": 1000 * df["co2_kg"].sum()
        / (df["seats"] * df["distance_km"]).sum(),
    }


def monthly(df: pd.DataFrame) -> pd.DataFrame:
    df = df if "co2_kg" in df else add_emissions(df)
    g = df.groupby(df["date"].dt.to_period("M").dt.to_timestamp())
    out = pd.DataFrame({
        "flights": g.size(),
        "punctuality_pct": g["arr_delay_min"].apply(
            lambda s: 100 * (s <= PUNCTUALITY_THRESHOLD_MIN).mean()),
        "atfm_per_flight": g["atfm_delay_min"].mean(),
        "add_taxi_min": g["add_taxi_min"].mean(),
        "co2_add_taxi_t": g["co2_add_taxi_kg"].sum() / 1000,
    })
    out.index.name = "month"
    return out.reset_index()


def delay_by_cause(df: pd.DataFrame, causes: dict) -> pd.DataFrame:
    reg = df[df["atfm_delay_min"] > 0]
    out = reg.groupby("atfm_cause")["atfm_delay_min"].agg(["sum", "count"])
    out["share_pct"] = 100 * out["sum"] / out["sum"].sum()
    out["cause"] = out.index.map(causes)
    return out.reset_index().sort_values("sum", ascending=False)


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Additive sums per departure airport and month.

    Every headline KPI can be rebuilt exactly from these sums, so a report or
    web page can filter and combine airports/months without the raw flights.
    """
    df = df if "co2_kg" in df else add_emissions(df)
    df = df.assign(
        month=df["date"].dt.to_period("M").astype(str),
        punctual=(df["arr_delay_min"] <= PUNCTUALITY_THRESHOLD_MIN).astype(int),
        regulated=(df["atfm_delay_min"] > 0).astype(int),
        seat_km=df["seats"] * df["distance_km"],
    )
    return (df.groupby(["adep", "month"])
              .agg(flights=("flight_id", "size"), punctual=("punctual", "sum"),
                   atfm_min=("atfm_delay_min", "sum"), regulated=("regulated", "sum"),
                   add_taxi_min=("add_taxi_min", "sum"), co2_kg=("co2_kg", "sum"),
                   co2_add_taxi_kg=("co2_add_taxi_kg", "sum"), seat_km=("seat_km", "sum"))
              .reset_index())


def summary_from_aggregate(agg: pd.DataFrame) -> dict:
    s = agg.sum(numeric_only=True)
    return {
        "flights": int(s["flights"]),
        "punctuality_pct": 100 * s["punctual"] / s["flights"],
        "atfm_per_flight": s["atfm_min"] / s["flights"],
        "regulated_pct": 100 * s["regulated"] / s["flights"],
        "avg_delay_regulated": s["atfm_min"] / s["regulated"] if s["regulated"] else 0.0,
        "add_taxi_min": s["add_taxi_min"] / s["flights"],
        "co2_t": s["co2_kg"] / 1000,
        "co2_g_per_seat_km": 1000 * s["co2_kg"] / s["seat_km"],
    }


def airport_ranking(df: pd.DataFrame) -> pd.DataFrame:
    df = df if "co2_kg" in df else add_emissions(df)
    g = df.groupby("adep")
    out = pd.DataFrame({
        "departures": g.size(),
        "atfm_per_flight": g["atfm_delay_min"].mean(),
        "punctuality_pct": g["arr_delay_min"].apply(
            lambda s: 100 * (s <= PUNCTUALITY_THRESHOLD_MIN).mean()),
        "add_taxi_min": g["add_taxi_min"].mean(),
        "co2_add_taxi_t": g["co2_add_taxi_kg"].sum() / 1000,
    })
    return out.sort_values("atfm_per_flight", ascending=False).round(2).reset_index()
