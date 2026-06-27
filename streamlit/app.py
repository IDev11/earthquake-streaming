import os
import time

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(
    page_title="Earthquake Monitor",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* ── Hide Streamlit chrome ── */
header[data-testid="stHeader"]  { display: none !important; }
[data-testid="stToolbar"]        { display: none !important; }
[data-testid="stDeployButton"]   { display: none !important; }
#MainMenu                         { display: none !important; }
footer                            { display: none !important; }

/* ── Base ── */
.stApp { background: #060c18; }
.block-container { padding: 1.6rem 2.4rem 2rem !important; max-width: 100% !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #090f1e !important;
    border-right: 1px solid #131e32 !important;
}

/* Widget labels only — NOT caption or description text */
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    color: #4a6888 !important;
    font-size: 0.7rem !important;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.9px;
}

/* Sidebar body text (captions, descriptions) — normal case */
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color: #2e4560 !important;
    font-size: 0.75rem !important;
    line-height: 1.55 !important;
    text-transform: none !important;
    letter-spacing: normal !important;
}

/* Sidebar heading / section name */
[data-testid="stSidebar"] h3 {
    color: #7a9ec4 !important;
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    margin-bottom: 2px !important;
}

/* Sidebar selectbox — dark background */
[data-testid="stSidebar"] [data-baseweb="select"] > div:first-child {
    background: #0d1828 !important;
    border-color: #1a2e48 !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] div[class*="ValueContainer"] {
    color: #8aaac8 !important;
}
/* Dropdown menu */
[data-baseweb="popover"] li { background: #0d1828 !important; color: #8aaac8 !important; }
[data-baseweb="popover"] li:hover,
[data-baseweb="popover"] li[aria-selected="true"] { background: #152035 !important; }

/* ── Metric cards ── */
[data-testid="stMetric"] {
    background: #0a1525;
    border: 1px solid #152030;
    border-radius: 8px;
    padding: 14px 18px;
}
[data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: #d0e8ff !important;
    letter-spacing: -0.3px;
}
[data-testid="stMetricLabel"] {
    font-size: 0.65rem !important;
    color: #3d5878 !important;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    font-weight: 600;
}

/* ── Page title ── */
h1 {
    color: #c8e0f8 !important;
    font-weight: 700 !important;
    font-size: 1.4rem !important;
    letter-spacing: -0.3px;
    margin-bottom: 0 !important;
}

/* ── Section labels ── */
.section-label {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #2e4a68;
    margin: 0 0 0.55rem 0;
    padding: 0;
    line-height: 1;
}

/* ── Divider ── */
hr { border-color: #0e1a2c !important; margin: 1rem 0 !important; }

/* ── Tables ── */
[data-testid="stDataFrame"] {
    border: 1px solid #0e1a2c !important;
    border-radius: 8px;
    overflow: hidden;
}

/* ── Alerts ── */
.stAlert { border-radius: 8px !important; border: none !important; }

/* ── Plotly ── */
.js-plotly-plot { border-radius: 8px; overflow: hidden; }

/* ── Captions ── */
.stCaption, [data-testid="stCaptionContainer"] p {
    color: #243850 !important;
    font-size: 0.67rem !important;
}
</style>
""", unsafe_allow_html=True)

PG_URL = (
    f"postgresql+psycopg2://{os.environ.get('PG_USER','quake')}:"
    f"{os.environ.get('PG_PASSWORD','quake')}@"
    f"{os.environ.get('PG_HOST','localhost')}:"
    f"{os.environ.get('PG_PORT','5432')}/"
    f"{os.environ.get('PG_DB','earthquakes')}"
)


@st.cache_resource
def get_engine():
    return create_engine(PG_URL)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Earthquake Monitor")
    st.caption("USGS · M2.5+ · Real-time")
    st.divider()

    st.markdown(
        "<p style='font-size:0.65rem;font-weight:700;text-transform:uppercase;"
        "letter-spacing:1.4px;color:#2e4a68;margin:0 0 0.5rem'>Display</p>",
        unsafe_allow_html=True,
    )
    time_window = st.selectbox(
        "Time window",
        ["Last 1 hour", "Last 6 hours", "Last 24 hours", "Last 7 days"],
        index=2,
    )
    window_map = {"Last 1 hour": 1, "Last 6 hours": 6, "Last 24 hours": 24, "Last 7 days": 168}
    window_hours = window_map[time_window]

    auto_refresh = st.toggle("Auto-refresh", value=True)
    refresh_secs = st.select_slider(
        "Refresh interval",
        options=[30, 60, 120, 300],
        value=60,
        format_func=lambda s: f"{s} s",
        disabled=not auto_refresh,
    )

    st.divider()
    st.markdown(
        "<p style='font-size:0.65rem;font-weight:700;text-transform:uppercase;"
        "letter-spacing:1.4px;color:#2e4a68;margin:0 0 0.4rem'>Swarm Detection</p>",
        unsafe_allow_html=True,
    )
    st.caption("A swarm is a cluster of events concentrated in the same area within a short window.")

    swarm_min_events = st.slider("Min events in cluster", 3, 30, 10)
    swarm_radius_km  = st.slider("Cluster radius", 10, 200, 50, format="%d km")
    swarm_window_h   = st.slider("Time window", 1, 24, 1, format="%d h")
    grid_deg = round(swarm_radius_km / 111, 3)


# ── Data ───────────────────────────────────────────────────────────────────────
def table_exists() -> bool:
    q = text("""SELECT EXISTS(SELECT 1 FROM information_schema.tables
                WHERE table_schema='raw' AND table_name='earthquakes')""")
    with get_engine().connect() as c:
        return c.execute(q).scalar()


def load_events(hours: int) -> pd.DataFrame:
    q = text(f"""
        SELECT event_id, magnitude, place, event_time,
               latitude, longitude, depth_km, tsunami, title
        FROM raw.earthquakes
        WHERE event_time >= NOW() - INTERVAL '{hours} hours'
        ORDER BY event_time DESC
    """)
    with get_engine().connect() as c:
        return pd.read_sql(q, c)


def load_swarms(window_h: int, min_events: int, grid: float) -> pd.DataFrame:
    q = text(f"""
        WITH w AS (
            SELECT magnitude, event_time,
                ROUND(CAST(latitude  / {grid} AS numeric), 0) * {grid} AS lat_cell,
                ROUND(CAST(longitude / {grid} AS numeric), 0) * {grid} AS lon_cell
            FROM raw.earthquakes
            WHERE event_time >= NOW() - INTERVAL '{window_h} hours'
        )
        SELECT lat_cell AS latitude, lon_cell AS longitude,
               COUNT(*) AS event_count,
               ROUND(MAX(magnitude)::numeric, 1) AS max_magnitude,
               ROUND(AVG(magnitude)::numeric, 1) AS avg_magnitude,
               ROUND(EXTRACT(EPOCH FROM (MAX(event_time) - MIN(event_time))) / 60) AS duration_minutes
        FROM w
        GROUP BY lat_cell, lon_cell
        HAVING COUNT(*) >= {min_events}
        ORDER BY event_count DESC
    """)
    with get_engine().connect() as c:
        return pd.read_sql(q, c)


# ── Color / size ───────────────────────────────────────────────────────────────
_SCALE = [
    (7.0, [190,  0, 245, 240]),
    (6.0, [215, 20,  20, 235]),
    (5.0, [255, 115,  0, 225]),
    (4.0, [250, 205,  0, 210]),
    (0.0, [ 50, 205, 110, 195]),
]

def mag_color(mag):
    if pd.isna(mag):
        return [100, 120, 145, 140]
    for threshold, color in _SCALE:
        if mag >= threshold:
            return color
    return _SCALE[-1][1]


def mag_radius(mag):
    if pd.isna(mag):
        return 35_000
    return max(35_000, mag ** 2 * 7_000)


# ── Guards ─────────────────────────────────────────────────────────────────────
if not table_exists():
    st.info("Pipeline warming up — waiting for first events.")
    time.sleep(10)
    st.rerun()

df     = load_events(window_hours)
swarms = load_swarms(swarm_window_h, swarm_min_events, grid_deg)

if df.empty:
    st.warning("No events in this window yet. The pipeline may still be warming up.")
    time.sleep(15)
    st.rerun()


# ── Header ─────────────────────────────────────────────────────────────────────
title_col, meta_col = st.columns([3, 1])
with title_col:
    st.markdown("# Global Earthquake Monitor")
with meta_col:
    st.markdown(
        f"<div style='text-align:right;padding-top:6px;"
        f"color:#3a5878;font-size:0.72rem;line-height:1.6'>"
        f"{time_window} &nbsp;·&nbsp; {len(df):,} events<br>"
        f"Updated {pd.Timestamp.utcnow().strftime('%H:%M')} UTC"
        f"</div>",
        unsafe_allow_html=True,
    )

st.divider()

# ── KPI tiles ─────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Events",   f"{len(df):,}")
k2.metric("Strongest",      f"M {df['magnitude'].max():.1f}")
k3.metric("Avg Magnitude",  f"M {df['magnitude'].mean():.2f}")
k4.metric("Avg Depth",      f"{df['depth_km'].mean():.1f} km")
k5.metric("Active Swarms",  len(swarms))

st.divider()

# ── Globe ──────────────────────────────────────────────────────────────────────
df["color"]          = df["magnitude"].apply(mag_color)
df["radius"]         = df["magnitude"].apply(mag_radius)
df["glow_radius"]    = df["radius"] * 2.4
df["glow_color"]     = df["color"].apply(lambda c: [c[0], c[1], c[2], 28])
df["event_time_str"] = df["event_time"].astype(str).str[:19]

layers = [
    pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["longitude", "latitude"],
        get_radius="glow_radius",
        get_fill_color="glow_color",
        pickable=False,
        stroked=False,
    ),
    pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["longitude", "latitude"],
        get_radius="radius",
        get_fill_color="color",
        pickable=True,
        stroked=True,
        get_line_color=[255, 255, 255, 40],
        line_width_min_pixels=0.5,
    ),
]

if not swarms.empty:
    swarms["swarm_radius"] = swarm_radius_km * 1_000
    layers.append(pdk.Layer(
        "ScatterplotLayer",
        data=swarms,
        get_position=["longitude", "latitude"],
        get_radius="swarm_radius",
        get_fill_color=[255, 80, 0, 15],
        get_line_color=[255, 100, 0, 210],
        stroked=True,
        filled=True,
        line_width_min_pixels=2,
    ))

st.pydeck_chart(
    pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(latitude=15, longitude=10, zoom=0.6),
        views=[pdk.View(type="GlobeView", controller=True)],
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        tooltip={
            "html": (
                "<div style='font-family:-apple-system,BlinkMacSystemFont,sans-serif;"
                "padding:8px 12px;background:#080f1e;border:1px solid #1c3050;"
                "border-radius:8px;min-width:210px;line-height:1.7'>"
                "<div style='color:#b8d0ec;font-size:12.5px;font-weight:600;"
                "margin-bottom:4px'>{title}</div>"
                "<div style='font-size:11.5px'>"
                "<span style='color:#456080'>Magnitude</span> "
                "<span style='color:#e0f0ff;font-weight:600'>{magnitude}</span>"
                "&ensp;"
                "<span style='color:#456080'>Depth</span> "
                "<span style='color:#e0f0ff;font-weight:600'>{depth_km} km</span>"
                "</div>"
                "<div style='color:#2e4a68;font-size:10.5px;margin-top:3px'>{event_time_str} UTC</div>"
                "</div>"
            ),
            "style": {"backgroundColor": "transparent", "border": "none"},
        },
    ),
    use_container_width=True,
)

# Compact legend
st.markdown(
    "<div style='display:flex;justify-content:center;gap:20px;"
    "font-size:0.68rem;color:#2e4a68;margin-top:4px;letter-spacing:0.3px'>"
    "<span><span style='color:#32cd6e'>&#9679;</span>&ensp;M &lt; 4</span>"
    "<span><span style='color:#facd00'>&#9679;</span>&ensp;M 4–5</span>"
    "<span><span style='color:#ff7300'>&#9679;</span>&ensp;M 5–6</span>"
    "<span><span style='color:#d71414'>&#9679;</span>&ensp;M 6–7</span>"
    "<span><span style='color:#be00f5'>&#9679;</span>&ensp;M 7+</span>"
    "<span style='margin-left:10px'>"
    "<span style='color:#ff6400'>&#9675;</span>&ensp;Swarm zone</span>"
    "</div>",
    unsafe_allow_html=True,
)

st.divider()

# ── Analytics row ──────────────────────────────────────────────────────────────
hist_col, swarm_col = st.columns([3, 2])

with hist_col:
    st.markdown('<p class="section-label">Magnitude Distribution</p>', unsafe_allow_html=True)
    fig = px.histogram(df, x="magnitude", nbins=28, color_discrete_sequence=["#e05c10"])
    fig.update_traces(marker_line_width=0.4, marker_line_color="#ff8030")
    fig.update_layout(
        paper_bgcolor="#080f1e",
        plot_bgcolor="#080f1e",
        font=dict(color="#8aaac8", size=11),
        bargap=0.06,
        margin=dict(l=0, r=0, t=4, b=0),
        xaxis=dict(gridcolor="#0e1c30", title="Magnitude", title_font_color="#3d5f80", tickcolor="#1a2e48"),
        yaxis=dict(gridcolor="#0e1c30", title="Events",    title_font_color="#3d5f80", tickcolor="#1a2e48"),
        height=240,
    )
    st.plotly_chart(fig, use_container_width=True)

with swarm_col:
    swarm_header = (
        f'<p class="section-label">Swarm Clusters'
        f'<span style="font-weight:400;color:#1e3858;margin-left:8px">'
        f'{len(swarms)} detected</span></p>'
    )
    st.markdown(swarm_header, unsafe_allow_html=True)

    if swarms.empty:
        st.markdown(
            f"<div style='color:#2e4a68;font-size:0.82rem;padding:14px 16px;"
            f"background:#080f1e;border:1px solid #0e1c30;border-radius:8px;"
            f"line-height:1.6;margin-top:2px'>"
            f"No clusters detected with current settings<br>"
            f"<span style='color:#1e3858'>"
            f"&ge;{swarm_min_events} events &nbsp;·&nbsp; "
            f"{swarm_radius_km} km radius &nbsp;·&nbsp; "
            f"{swarm_window_h}h window</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        display = swarms[[
            "latitude", "longitude", "event_count",
            "max_magnitude", "avg_magnitude", "duration_minutes",
        ]].rename(columns={
            "latitude": "Lat", "longitude": "Lon",
            "event_count": "Events",
            "max_magnitude": "Max M", "avg_magnitude": "Avg M",
            "duration_minutes": "Duration (min)",
        })
        st.dataframe(display, use_container_width=True, hide_index=True, height=240)

st.divider()

# ── Recent events ──────────────────────────────────────────────────────────────
st.markdown('<p class="section-label">Recent Events</p>', unsafe_allow_html=True)

table_df = df[["event_time_str", "magnitude", "depth_km", "place", "tsunami"]].rename(columns={
    "event_time_str": "Time (UTC)",
    "magnitude":      "Magnitude",
    "depth_km":       "Depth (km)",
    "place":          "Location",
    "tsunami":        "Tsunami",
})
st.dataframe(
    table_df.head(100),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Magnitude": st.column_config.NumberColumn(format="%.1f"),
        "Depth (km)": st.column_config.NumberColumn(format="%.1f"),
        "Tsunami": st.column_config.CheckboxColumn(),
    },
)

if auto_refresh:
    time.sleep(refresh_secs)
    st.rerun()
