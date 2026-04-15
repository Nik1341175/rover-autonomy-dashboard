import streamlit as st
import pandas as pd
import psycopg2
from psycopg2 import Error
import plotly.express as px
import plotly.graph_objects as go
import json
from datetime import datetime, timedelta
 
# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="🤖 RoverX Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)
 
st.title("🤖 RoverX Autonomous Rover - Live Mission Dashboard")
st.markdown("Wildlife & Object Detection Mission Control")
st.markdown("---")
 
# ============================================================================
# PASSKEY AUTHENTICATION
# ============================================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
 
if not st.session_state.authenticated:
    st.warning("🔐 This dashboard is password protected")
    passkey = st.text_input("Enter Passkey:", type="password")
    
    if st.button("Login"):
        if passkey == st.secrets.get("passkey", "roverx2026"):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ Invalid passkey!")
    st.stop()
 
# ============================================================================
# DATABASE CONNECTION
# ============================================================================
@st.cache_resource
def get_db_connection():
    """Create connection to Pukki DBaaS"""
    try:
        conn = psycopg2.connect(
            host=st.secrets["db"]["host"],
            port=st.secrets["db"]["port"],
            database=st.secrets["db"]["dbname"],
            user=st.secrets["db"]["user"],
            password=st.secrets["db"]["password"],
            sslmode="require"
        )
        return conn
    except Error as e:
        st.error(f"❌ Database connection error: {e}")
        return None
 
@st.cache_data(ttl=10)  # Refresh every 10 seconds for near real-time
def fetch_roverx_data():
    """Fetch RoverX telemetry data from database"""
    conn = get_db_connection()
    if conn is None:
        return None
    
    try:
        query = """
        SELECT id, timestamp, latitude, longitude, gps_speed, 
               battery_voltage, battery_current, rover_mode,
               detected_objects, lidar_distance, decision_made, 
               confidence_score, camera_frame_path
        FROM roverx_telemetry 
        ORDER BY timestamp DESC
        """
        df = pd.read_sql(query, conn)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Error as e:
        st.error(f"❌ Query error: {e}")
        return None
    finally:
        if conn:
            conn.close()
 
# ============================================================================
# FETCH DATA
# ============================================================================
df = fetch_roverx_data()
 
if df is None or df.empty:
    st.error("❌ No telemetry data found. Please run setup_roverx.py first to populate the database.")
    st.stop()
 
st.success(f"✓ Connected! Loaded {len(df)} telemetry records")
 
# ============================================================================
# SIDEBAR CONTROLS
# ============================================================================
st.sidebar.header("📊 Mission Controls")
 
time_range = st.sidebar.slider(
    "Time Range (last N hours):",
    min_value=1,
    max_value=24,
    value=2
)
 
mode_filter = st.sidebar.multiselect(
    "Filter by Rover Mode:",
    options=df['rover_mode'].unique(),
    default=df['rover_mode'].unique()
)
 
show_detections_only = st.sidebar.checkbox("Show Only Detections", value=False)
 
df_filtered = df[
    (df['timestamp'] >= pd.Timestamp.now() - pd.Timedelta(hours=time_range)) &
    (df['rover_mode'].isin(mode_filter))
]
 
if show_detections_only:
    df_filtered = df_filtered[df_filtered['detected_objects'].notna()]
 
# ============================================================================
# CURRENT STATUS SECTION
# ============================================================================
st.header("📡 Current Mission Status")
 
if not df_filtered.empty:
    latest = df_filtered.iloc[0]
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("🤖 Rover Mode", latest['rover_mode'])
    
    with col2:
        st.metric("🔋 Battery", f"{latest['battery_voltage']:.1f}V")
    
    with col3:
        st.metric("⚡ Current", f"{latest['battery_current']:.2f}A")
    
    with col4:
        st.metric("🚗 Speed", f"{latest['gps_speed']:.2f} m/s")
    
    with col5:
        if latest['detected_objects'] is not None:
            try:
                obj_data = json.loads(latest['detected_objects'])
                st.metric("🎯 Last Detection", obj_data['object'].upper())
            except:
                st.metric("🎯 Last Detection", "Unknown")
        else:
            st.metric("🎯 Last Detection", "None")
    
    st.markdown("---")
 
# ============================================================================
# DETECTION INSIGHTS
# ============================================================================
st.header("🔍 Object Detection Insights")
 
# Parse detected objects
detections_list = []
for idx, row in df_filtered.iterrows():
    if row['detected_objects'] is not None:
        try:
            obj = json.loads(row['detected_objects'])
            detections_list.append({
                'timestamp': row['timestamp'],
                'object': obj['object'],
                'confidence': obj['confidence'],
                'decision': row['decision_made']
            })
        except:
            pass
 
if detections_list:
    detections_df = pd.DataFrame(detections_list)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📊 Detection Count by Object")
        object_counts = detections_df['object'].value_counts()
        fig_objects = px.bar(
            x=object_counts.index,
            y=object_counts.values,
            labels={'x': 'Object Type', 'y': 'Count'},
            title="Objects Detected During Mission",
            color=object_counts.index
        )
        st.plotly_chart(fig_objects, use_container_width=True)
    
    with col2:
        st.subheader("📈 Average Confidence by Object")
        avg_confidence = detections_df.groupby('object')['confidence'].mean()
        fig_confidence = px.bar(
            x=avg_confidence.index,
            y=avg_confidence.values,
            labels={'x': 'Object Type', 'y': 'Avg Confidence'},
            title="Model Confidence Scores",
            color_discrete_sequence=["#639922"]
        )
        st.plotly_chart(fig_confidence, use_container_width=True)
    
    with col3:
        st.subheader("🎬 Decisions Made")
        decision_counts = detections_df['decision'].value_counts()
        fig_decisions = px.pie(
            values=decision_counts.values,
            names=decision_counts.index,
            title="Rover Decisions",
            hole=0.3
        )
        st.plotly_chart(fig_decisions, use_container_width=True)
    
    st.markdown("---")
else:
    st.info("No detections in the selected time range. The rover is operating in clear conditions.")
 
# ============================================================================
# REAL-TIME CHARTS
# ============================================================================
st.header("📈 Real-Time Telemetry")
 
col1, col2 = st.columns(2)
 
with col1:
    st.subheader("🔋 Battery Voltage Over Time")
    fig_battery = px.line(
        df_filtered.sort_values('timestamp'),
        x='timestamp',
        y='battery_voltage',
        title="Battery Discharge Curve",
        labels={'battery_voltage': 'Voltage (V)', 'timestamp': 'Time'},
        markers=True
    )
    fig_battery.add_hline(y=11.0, line_dash="dash", line_color="red", annotation_text="Low Battery Threshold")
    st.plotly_chart(fig_battery, use_container_width=True)
 
with col2:
    st.subheader("⚡ Current Draw Over Time")
    fig_current = px.line(
        df_filtered.sort_values('timestamp'),
        x='timestamp',
        y='battery_current',
        title="Power Consumption",
        labels={'battery_current': 'Current (A)', 'timestamp': 'Time'},
        markers=True,
        line_shape="spline"
    )
    st.plotly_chart(fig_current, use_container_width=True)
 
col1, col2 = st.columns(2)
 
with col1:
    st.subheader("🚗 Speed Profile")
    fig_speed = px.bar(
        df_filtered.sort_values('timestamp'),
        x='timestamp',
        y='gps_speed',
        title="Rover Speed",
        labels={'gps_speed': 'Speed (m/s)', 'timestamp': 'Time'},
        color='gps_speed',
        color_continuous_scale='Viridis'
    )
    st.plotly_chart(fig_speed, use_container_width=True)
 
with col2:
    st.subheader("📡 LiDAR Distance to Obstacles")
    lidar_data = df_filtered[df_filtered['lidar_distance'].notna()]
    if not lidar_data.empty:
        fig_lidar = px.scatter(
            lidar_data,
            x='timestamp',
            y='lidar_distance',
            title="Distance to Nearest Obstacle",
            labels={'lidar_distance': 'Distance (cm)', 'timestamp': 'Time'},
            size='lidar_distance',
            hover_data=['rover_mode', 'decision_made']
        )
        fig_lidar.add_hline(y=50, line_dash="dash", line_color="red", annotation_text="Stop Distance")
        st.plotly_chart(fig_lidar, use_container_width=True)
    else:
        st.info("No LiDAR data available for selected period")
 
st.markdown("---")
 
# ============================================================================
# GPS TRAJECTORY
# ============================================================================
st.header("🗺️ Mission Trajectory")
 
if not df_filtered.empty:
    st.subheader("GPS Path with Detection Markers")
    
    # Prepare map data
    map_data = df_filtered[['latitude', 'longitude']].copy()
    
    # Add detection markers
    fig_map = px.scatter_mapbox(
        df_filtered,
        lat='latitude',
        lon='longitude',
        hover_name='timestamp',
        hover_data=['rover_mode', 'decision_made', 'gps_speed'],
        color='battery_voltage',
        size='lidar_distance',
        color_continuous_scale="RdYlGn",
        zoom=13,
        title="RoverX Mission Path",
        mapbox_style="open-street-map"
    )
    
    st.plotly_chart(fig_map, use_container_width=True)
    
    # Show distance traveled
    if len(df_filtered) > 1:
        total_distance = 0
        for i in range(len(df_filtered) - 1):
            lat1 = df_filtered.iloc[i]['latitude']
            lon1 = df_filtered.iloc[i]['longitude']
            lat2 = df_filtered.iloc[i+1]['latitude']
            lon2 = df_filtered.iloc[i+1]['longitude']
            
            # Simple distance calculation (meters, approximate)
            distance = ((lat2-lat1)**2 + (lon2-lon1)**2)**0.5 * 111000
            total_distance += distance
        
        st.metric("📏 Total Distance Traveled", f"{total_distance:.1f} m")
 
st.markdown("---")
 
# ============================================================================
# ROVER MODE ANALYSIS
# ============================================================================
st.header("🎛️ Rover Mode Breakdown")
 
mode_counts = df_filtered['rover_mode'].value_counts()
fig_modes = px.pie(
    values=mode_counts.values,
    names=mode_counts.index,
    title="Time Spent in Each Mode",
    hole=0.3,
    color_discrete_map={
        "Autonomous": "#639922",
        "Manual Override": "#2E75B6",
        "Standby": "#FFC000",
        "Error": "#A32D2D"
    }
)
st.plotly_chart(fig_modes, use_container_width=True)
 
st.markdown("---")
 
# ============================================================================
# DETAILED DATA TABLE
# ============================================================================
st.header("📋 Detailed Mission Log")
 
# Format the display data
display_df = df_filtered.sort_values('timestamp', ascending=False).copy()
display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
display_df['detected_object'] = display_df['detected_objects'].apply(
    lambda x: json.loads(x)['object'] if pd.notna(x) else 'None'
)
 
display_cols = ['timestamp', 'rover_mode', 'detected_object', 'decision_made', 
                'confidence_score', 'battery_voltage', 'lidar_distance', 'gps_speed']
st.dataframe(
    display_df[display_cols],
    use_container_width=True,
    height=400
)
 
st.markdown("---")
 
# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.markdown("🤖 **RoverX Autonomous Rover Dashboard** | Powered by Streamlit + Pukki DBaaS")
st.markdown(f"Last updated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")