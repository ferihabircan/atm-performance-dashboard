import pandas as pd
import pytest

from atm_kpi import data, kpis


@pytest.fixture(scope="module")
def flights():
    return data.generate(months=2, flights_per_day=60, seed=3)


def test_schema(flights):
    assert list(flights.columns) == data.COLUMNS
    assert (flights["adep"] != flights["ades"]).all()
    assert (flights.loc[flights["atfm_delay_min"] == 0, "atfm_cause"] == "").all()


def test_punctuality_on_hand_made_data():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-01"] * 4), "adep": "EBBR", "ades": "EHAM",
        "aircraft_type": "A320", "seats": 180, "distance_km": 100,
        "atfm_delay_min": [0, 0, 10, 30], "atfm_cause": ["", "", "C", "W"],
        "taxi_out_min": [10, 12, 10, 15], "unimpeded_taxi_min": 10,
        "arr_delay_min": [0, 15, 16, 40],
    })
    s = kpis.summary(df)
    assert s["punctuality_pct"] == 50          # 0 and 15 are on time
    assert s["atfm_per_flight"] == 10
    assert s["regulated_pct"] == 50
    assert s["avg_delay_regulated"] == 20
    assert s["add_taxi_min"] == pytest.approx(1.75)


def test_co2_formula():
    df = pd.DataFrame({"aircraft_type": ["A320"], "distance_km": [1000],
                       "taxi_out_min": [12.0], "unimpeded_taxi_min": [10.0]})
    e = kpis.add_emissions(df).iloc[0]
    lto, per_km, taxi = kpis.FUEL["A320"]
    assert e["fuel_kg"] == pytest.approx(lto + per_km * 1000 + taxi * 2)
    assert e["co2_kg"] == pytest.approx(e["fuel_kg"] * 3.16)


def test_cause_shares_sum_to_100(flights):
    c = kpis.delay_by_cause(flights, data.CAUSES)
    assert c["share_pct"].sum() == pytest.approx(100)


def test_csv_roundtrip(tmp_path, flights):
    p = tmp_path / "f.csv"
    flights.to_csv(p, index=False)
    back = data.load(p)
    assert kpis.summary(back)["flights"] == len(flights)
    assert kpis.summary(back)["co2_t"] == pytest.approx(kpis.summary(flights)["co2_t"])
