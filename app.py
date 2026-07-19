"""Garage Print Window — Shiny for Python dashboard.

Answers: how many hours/day can I reliably 3D print in the garage, and how much
does each hardware intervention widen that window?

Data source is automatic:
  * If the live ruuvi SQLite DB is present (running on the Mac mini), read it
    directly and refresh periodically -> a near-realtime "live pivot table."
  * Otherwise (e.g. deployed to shinyapps.io) fall back to the CSV snapshot
    produced by extract_data.py.
"""
import os
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from shiny import App, reactive, render, ui

HERE = Path(__file__).parent
CSV = HERE / "data" / "garage_readings.csv"
DB = Path(os.path.expanduser("~/Programming-pavdog/ruuvi/data/ruuvi.db"))
REFRESH_SECS = 60          # how often to re-read when running live
TEMP_MAX = 86.0            # PLA upper ambient limit (°F)
HUM_MAX = 45.0             # filament dry limit (% RH)

PIVOT_SQL = """
WITH t AS (SELECT strftime('%Y-%m-%d %H:%M', ts, 'localtime') m, AVG(value) temp_f
           FROM readings WHERE metric='garage_temp_f' GROUP BY m),
     h AS (SELECT strftime('%Y-%m-%d %H:%M', ts, 'localtime') m, AVG(value) humidity
           FROM readings WHERE metric='garage_humidity' GROUP BY m)
SELECT t.m AS ts, t.temp_f, h.humidity FROM t JOIN h ON t.m=h.m ORDER BY t.m;
"""


def load_readings():
    """Return (dataframe, source_label). Live DB if present, else CSV snapshot.

    Set GARAGE_FORCE_CSV=1 to force the snapshot source (useful for demoing the
    deployed behavior locally).
    """
    if DB.exists() and not os.environ.get("GARAGE_FORCE_CSV"):
        try:
            con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
            df = pd.read_sql_query(PIVOT_SQL, con, parse_dates=["ts"])
            con.close()
            if len(df):
                return df, "LIVE — ruuvi.db"
        except Exception:
            pass
    return pd.read_csv(CSV, parse_dates=["ts"]), "Snapshot — CSV"


app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_radio_buttons(
            "scenario",
            "Hardware scenario",
            {
                "ambient": "Ambient — no hardware",
                "ams": "AMS 2 Pro — humidity solved",
                "ams_mini": "AMS + Mr Cool mini-split (projected)",
            },
            selected="ambient",
        ),
        ui.input_slider("cold", "PLA cold limit (°F, TBD)", min=32, max=75, value=50),
        ui.hr(),
        ui.markdown("**Printable when** temp is between the cold limit and **86°F** "
                    "*and* humidity is under **45%**."),
        ui.output_text("source"),
        width=320,
    ),
    ui.layout_columns(
        ui.value_box("Printable", ui.output_text("vb_pct")),
        ui.value_box("Hours / day", ui.output_text("vb_hrs")),
        ui.value_box("Dominant blocker", ui.output_text("vb_block")),
        fill=False,
    ),
    ui.card(ui.card_header("Printable minutes by hour of day"), ui.output_plot("p_hour")),
    ui.card(ui.card_header("Temperature & humidity vs. thresholds"), ui.output_plot("p_ts")),
    title="Garage Print Window",
)


def server(input, output, session):
    @reactive.calc
    def raw():
        reactive.invalidate_later(REFRESH_SECS)   # periodic refresh -> realtime when live
        df, src = load_readings()
        df["hour"] = df["ts"].dt.hour
        return df, src

    @reactive.calc
    def data():
        d, _ = raw()
        d = d.copy()
        temp_ok = (d["temp_f"] < TEMP_MAX) & (d["temp_f"] > input.cold())
        hum_ok = d["humidity"] < HUM_MAX
        s = input.scenario()
        if s == "ambient":
            printable = temp_ok & hum_ok
        elif s == "ams":                          # desiccant removes humidity as a variable
            printable = temp_ok
        else:                                     # mini-split also holds temp in band
            printable = pd.Series(True, index=d.index)
        d["printable"] = printable.values
        d["temp_ok"], d["hum_ok"] = temp_ok.values, hum_ok.values
        return d

    @render.text
    def source():
        _, src = raw()
        return f"Data source: {src}"

    @render.text
    def vb_pct():
        return f"{100 * data()['printable'].mean():.1f}%"

    @render.text
    def vb_hrs():
        return f"{24 * data()['printable'].mean():.1f}"

    @render.text
    def vb_block():
        d = data()
        hum_block, temp_block = (~d["hum_ok"]).mean(), (~d["temp_ok"]).mean()
        if hum_block >= temp_block:
            return f"Humidity — {100 * hum_block:.0f}% of the time"
        return f"Temperature — {100 * temp_block:.0f}% of the time"

    @render.plot
    def p_hour():
        by = (data().groupby("hour")["printable"].mean()
              .reindex(range(24), fill_value=0) * 100)
        fig, ax = plt.subplots()
        ax.bar(by.index, by.values, color="#2a9d8f")
        ax.set_xlabel("Hour of day")
        ax.set_ylabel("% of minutes printable")
        ax.set_ylim(0, 100)
        ax.set_xticks(range(0, 24, 2))
        return fig

    @render.plot
    def p_ts():
        d = data()
        fig, (a1, a2) = plt.subplots(2, 1, sharex=True, figsize=(8, 5))
        a1.plot(d["ts"], d["temp_f"], color="#e76f51", lw=0.6)
        a1.axhline(TEMP_MAX, color="k", ls="--", lw=0.8, label="86°F")
        a1.axhline(input.cold(), color="b", ls="--", lw=0.8, label="cold limit")
        a1.set_ylabel("Temp °F")
        a1.legend(loc="upper right", fontsize=8)
        a2.plot(d["ts"], d["humidity"], color="#264653", lw=0.6)
        a2.axhline(HUM_MAX, color="k", ls="--", lw=0.8, label="45%")
        a2.set_ylabel("Humidity %")
        a2.legend(loc="upper right", fontsize=8)
        fig.autofmt_xdate()
        return fig


app = App(app_ui, server)
