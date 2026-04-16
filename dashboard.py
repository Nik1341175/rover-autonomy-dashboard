import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px

# ============================================================
# PAGE SETUP
# ============================================================
st.set_page_config(page_title="Rover Dashboard", layout="wide")
st.title("🤖 Rover Live Dashboard")

# ============================================================
# PASSKEY — stored in Streamlit secrets, never hardcoded
# ============================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pw = st.text_input("Enter passkey:", type="password")
    if st.button("Login"):
        if pw == st.secrets["passkey"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Wrong passkey")
    st.stop()

# ============================================================
# DATABASE CONNECTION
# @st.cache_resource means: connect once, reuse forever
# ============================================================
@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host     = st.secrets["db"]["host"],
        port     = st.secrets["db"]["port"],
        dbname   = st.secrets["db"]["dbname"],
        user     = st.secrets["db"]["user"],
        password = st.secrets["db"]["password"],
        sslmode  = "require"
    )

# ============================================================
# LOAD DATA
# @st.cache_data(ttl=3) means: re-fetch from DB every 3 seconds
# ============================================================
@st.cache_data(ttl=3)
def load_data():
    conn = get_connection()
    df = pd.read_sql("""
        SELECT * FROM rover_telemetry
        ORDER BY timestamp DESC
        LIMIT 300
    """, conn)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

# ============================================================
# FETCH AND CHECK
# ============================================================
df = load_data()

if df.empty:
    st.warning("No data yet. Is the rover running?")
    st.stop()

# Most recent row
latest = df.iloc[0]

# ============================================================
# TOP METRICS — snapshot of current state
# ============================================================
st.subheader("Current Status")
c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Speed",    f"{latest['speed']:.2f} m/s"  if latest['speed']   is not None else "—")
c2.metric("Battery",  f"{latest['battery_percent']:.1f}%" if latest['battery_percent'] is not None else "—")
c3.metric("Voltage",  f"{latest['battery_voltage']:.1f}V" if latest['battery_voltage'] is not None else "—")
c4.metric("LiDAR",    f"{latest['lidar_cm']:.0f} cm" if latest['lidar_cm'] is not None else "—")
c5.metric("Updated",  str(latest['timestamp'].strftime('%H:%M:%S')))

st.divider()

# ============================================================
# OBJECT DETECTION — what is the rover seeing right now?
# ============================================================
st.subheader("Object Detection")

# Find the most recent row that actually has a detection
detections = df[df["detected_object"].notna()]

if not detections.empty:
    last = detections.iloc[0]
    col1, col2 = st.columns(2)
    col1.metric("Detected Object", last["detected_object"].upper())
    col2.metric("Confidence",      f"{last['confidence']*100:.1f}%")
else:
    st.info("No object detected right now.")

st.divider()

# ============================================================
# GPS MAP
# ============================================================
st.subheader("GPS Path")

gps_df = df[df["latitude"].notna() & df["longitude"].notna()]

if not gps_df.empty:
    fig_map = px.scatter_mapbox(
        gps_df,
        lat="latitude",
        lon="longitude",
        color="speed",
        color_continuous_scale="Viridis",
        zoom=15,
        mapbox_style="open-street-map",
        hover_data=["timestamp", "speed"]
    )
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.info("No GPS data yet.")

st.divider()

# ============================================================
# CHARTS
# ============================================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("Speed over time")
    fig_speed = px.line(
        df.sort_values("timestamp"),
        x="timestamp", y="speed",
        labels={"speed": "m/s"}
    )
    st.plotly_chart(fig_speed, use_container_width=True)

with col2:
    st.subheader("LiDAR — obstacle distance")
    fig_lidar = px.line(
        df.sort_values("timestamp"),
        x="timestamp", y="lidar_cm",
        labels={"lidar_cm": "cm"},
        color_discrete_sequence=["orange"]
    )
    fig_lidar.add_hline(y=30, line_dash="dash", line_color="red",
                        annotation_text="Stop threshold")
    st.plotly_chart(fig_lidar, use_container_width=True)

col3, col4 = st.columns(2)

with col3:
    st.subheader("Battery voltage over time")
    fig_bat = px.line(
        df.sort_values("timestamp"),
        x="timestamp", y="battery_voltage",
        labels={"battery_voltage": "Volts"},
        color_discrete_sequence=["green"]
    )
    st.plotly_chart(fig_bat, use_container_width=True)

with col4:
    st.subheader("Detections breakdown")
    if not detections.empty:
        counts = detections["detected_object"].value_counts()
        fig_det = px.bar(
            x=counts.index, y=counts.values,
            labels={"x": "Object", "y": "Count"}
        )
        st.plotly_chart(fig_det, use_container_width=True)
    else:
        st.info("No detections recorded yet.")

st.divider()

# ============================================================
# RAW DATA TABLE
# ============================================================
with st.expander("Show raw data"):
    st.dataframe(df, use_container_width=True)