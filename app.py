"""Streamlit dashboard: streamlit run app.py"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from atm_kpi import data, kpis  # noqa: E402

st.set_page_config(page_title="ATM Performance & CO2", layout="wide")


@st.cache_data
def load_data(uploaded) -> pd.DataFrame:
    df = data.load(uploaded) if uploaded is not None else data.generate()
    return kpis.add_emissions(df)


st.title("European ATM Performance & CO2 Dashboard")
st.caption("Punctuality, ATFM delay, taxi-out efficiency and CO2. "
           "Synthetic demo data unless you upload a CSV in the documented schema.")

with st.sidebar:
    st.header("Filters")
    uploaded = st.file_uploader("Flight data (CSV)", type="csv")
    df_all = load_data(uploaded)
    airports = sorted(df_all["adep"].unique())
    sel = st.multiselect("Departure airports", airports, default=airports)
    dmin, dmax = df_all["date"].min().date(), df_all["date"].max().date()
    rng = st.date_input("Period", (dmin, dmax), min_value=dmin, max_value=dmax)

start, end = (rng if isinstance(rng, tuple) and len(rng) == 2 else (dmin, dmax))
df = df_all[df_all["adep"].isin(sel)
            & df_all["date"].between(pd.Timestamp(start), pd.Timestamp(end))]

if df.empty:
    st.warning("No flights match the filters.")
    st.stop()

s = kpis.summary(df)
c = st.columns(5)
c[0].metric("Flights", f"{s['flights']:,}")
c[1].metric("Punctuality (≤15 min)", f"{s['punctuality_pct']:.1f}%")
c[2].metric("ATFM delay / flight", f"{s['atfm_per_flight']:.2f} min")
c[3].metric("Add. taxi-out", f"{s['add_taxi_min']:.1f} min")
c[4].metric("CO2 / seat-km", f"{s['co2_g_per_seat_km']:.0f} g")

tab1, tab2, tab3 = st.tabs(["Trends", "Delay causes", "Airports"])

with tab1:
    m = kpis.monthly(df)
    left, right = st.columns(2)
    left.plotly_chart(px.line(m, x="month", y="punctuality_pct", markers=True,
                              title="Arrival punctuality (%)"),
                      use_container_width=True)
    right.plotly_chart(px.bar(m, x="month", y="atfm_per_flight",
                              title="ATFM delay per flight (min)"),
                       use_container_width=True)
    st.plotly_chart(px.bar(m, x="month", y="co2_add_taxi_t",
                           title="CO2 from additional taxi-out time (tonnes)"),
                    use_container_width=True)

with tab2:
    causes = kpis.delay_by_cause(df, data.CAUSES)
    st.plotly_chart(px.pie(causes, names="cause", values="sum", hole=0.45,
                           title="ATFM delay minutes by cause"),
                    use_container_width=True)
    st.write(f"{s['regulated_pct']:.1f}% of flights were regulated, with an "
             f"average of {s['avg_delay_regulated']:.1f} min for those flights.")

with tab3:
    ranking = kpis.airport_ranking(df)
    ranking["name"] = ranking["adep"].map(lambda a: data.AIRPORTS[a][0])
    ranking["lat"] = ranking["adep"].map(lambda a: data.AIRPORTS[a][1])
    ranking["lon"] = ranking["adep"].map(lambda a: data.AIRPORTS[a][2])
    fig = px.scatter_geo(ranking, lat="lat", lon="lon", size="departures",
                         color="atfm_per_flight", hover_name="name",
                         color_continuous_scale="OrRd", scope="europe",
                         title="ATFM delay per departure by airport",
                         size_max=30, height=520)
    fig.update_geos(fitbounds="locations", showcountries=True,
                    countrycolor="#999", showland=True, landcolor="#eceff3")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(ranking.drop(columns=["lat", "lon"]), use_container_width=True,
                 hide_index=True)
    st.download_button("Download airport KPIs (CSV)",
                       ranking.to_csv(index=False), "airport_kpis.csv")

with st.expander("Feedback (used for user testing sessions)"):
    st.radio("Did this dashboard answer your question?",
             ["Yes", "Partly", "No"], horizontal=True, key="fb_q")
    st.text_area("What is missing?", key="fb_text")
