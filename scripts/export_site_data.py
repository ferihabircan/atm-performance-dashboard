"""Export additive KPI aggregates to docs/data.json so the static website can
filter by airport and month in the browser without a Python server.

    PYTHONPATH=src python scripts/export_site_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

from atm_kpi import data, kpis

OUT = Path(__file__).resolve().parents[1] / "docs" / "data.json"


def main() -> None:
    df = kpis.add_emissions(data.generate())
    agg = kpis.aggregate(df)
    reg = df[df["atfm_delay_min"] > 0].assign(month=lambda d: d["date"].dt.to_period("M").astype(str))
    causes = (reg.groupby(["adep", "month", "atfm_cause"])["atfm_delay_min"].sum()
                 .round(1).reset_index())

    payload = {
        "airports": {k: {"name": v[0], "lat": v[1], "lon": v[2]} for k, v in data.AIRPORTS.items()},
        "causes": data.CAUSES,
        "threshold_min": kpis.PUNCTUALITY_THRESHOLD_MIN,
        # Columns kept positional to keep the file small.
        "agg_cols": list(agg.columns),
        "agg": agg.round(2).values.tolist(),
        "cause_rows": causes.values.tolist(),
        "check": {k: round(float(v), 4) for k, v in kpis.summary(df).items()},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print(payload["check"])


if __name__ == "__main__":
    main()
