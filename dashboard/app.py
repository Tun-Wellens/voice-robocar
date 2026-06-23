import streamlit as st
import pandas as pd
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from robocar_msgs.msg import GNSS 
import threading
import json
import time
import pydeck as pdk

# Basic Page Setup
st.set_page_config(layout="wide", page_title="Junior - Vehicle Dashboard")

# Shared Data State
@st.cache_resource
def get_shared_state():
    return {
        "car_lat": 49.6394, 
        "car_lon": 6.1684,
        "target_lat": None,
        "target_lon": None,
        "logs": []
    }

state = get_shared_state()

# Only set the map view once so the user can pan around freely!
if "view_state" not in st.session_state:
    st.session_state.view_state = pdk.ViewState(
        latitude=state["car_lat"], 
        longitude=state["car_lon"], 
        zoom=14, 
        pitch=0
    )

# Background ROS Connection
class DashboardNode(Node):
    def __init__(self, state_ref):
        super().__init__('streamlit_dashboard')
        self.state = state_ref
        self.create_subscription(GNSS, '/sensors/gnss', self.gnss_callback, 10)
        self.create_subscription(String, '/assistant/logs', self.log_callback, 10)

    def gnss_callback(self, msg):
        self.state["car_lat"] = msg.lat
        self.state["car_lon"] = msg.lon

    def log_callback(self, msg):
        try:
            log_data = json.loads(msg.data)
            self.state["logs"].insert(0, log_data) # Add to top
            
            if len(self.state["logs"]) > 50: # Keep memory clean
                self.state["logs"].pop()
            
            # If navigation triggered, update target on map
            if log_data.get("action") == "start_navigation":
                args = log_data.get("arguments", {})
                if "latitude" in args and "longitude" in args:
                    self.state["target_lat"] = args["latitude"]
                    self.state["target_lon"] = args["longitude"]
        except Exception as e:
            print(f"Error parsing log: {e}")

@st.cache_resource
def start_ros_thread():
    rclpy.init()
    node = DashboardNode(get_shared_state())
    thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    thread.start()
    return node

start_ros_thread()

# Helper to format timeline events
def render_log(log):
    """Turns technical logs into conversational, easy-to-read cards for the timeline."""
    log_type = log.get("type", "tool")
    
    if log_type == "speech_detected":
        summary = "Junior is listening..."
        color = "blue"
    elif log_type == "asr":
        text = log.get('text', '')
        summary = f"You asked: \"{text}\""
        color = "green"
    elif log_type == "tool":
        action = log.get('action', 'magic').replace('_', ' ').title()
        summary = f"Junior is using a tool ({action})..."
        color = "orange"
    elif log_type == "response":
        text = log.get('text', '')
        summary = f"Junior says: \"{text}\""
        color = "purple"
    else:
        summary = "Behind the scenes event"
        color = "gray"

    # Draw the expanding summary box so users can peek at the raw data if they want
    with st.expander(f"{summary}", expanded=False):
        st.json(log) # Keep the raw payload inside for debugging!

# Dashboard Layout and Welcome
st.title("Junior Voice Assistant Dashboard")
st.markdown("Watch Junior navigate and chat with you in real-time. Start talking to see him in action!")

col_map, col_logs = st.columns([2, 1])

with col_map:
    st.subheader("Where are we headed?")
    map_placeholder = st.empty()

with col_logs:
    st.subheader("Chat & Activity Timeline")
    logs_placeholder = st.empty()

# Live Re-render Loop
while True:
    # PyDeck Map Rendering
    # Car Layer (Blue dot, fixed pixel radius!)
    layers = [
        pdk.Layer(
            "ScatterplotLayer",
            data=[{"lat": state["car_lat"], "lon": state["car_lon"]}],
            get_position="[lon, lat]",
            get_color="[0, 0, 255, 255]",
            get_radius=20,          # Size in meters (base)
            radius_min_pixels=8,    # never get smaller than 8 pixels
            radius_max_pixels=15,   # never get bigger than 15 pixels
            pickable=True
        )
    ]
    
    # Destination Layer (Red dot)
    if state["target_lat"] and state["target_lon"]:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=[{"lat": state["target_lat"], "lon": state["target_lon"]}],
                get_position="[lon, lat]",
                get_color="[255, 0, 0, 255]",
                get_radius=20,
                radius_min_pixels=8,
                radius_max_pixels=15,
            )
        )
        
    with map_placeholder.container():
        # Using initial_view_state means it won't snap back when the user scrolls!
        deck = pdk.Deck(
            map_provider="carto",
            map_style="light",
            layers=layers,
            initial_view_state=st.session_state.view_state,
        )
        st.pydeck_chart(deck)

    # Render the Conversation Timeline
    with logs_placeholder.container():
        if not state["logs"]:
            st.info("It's quiet in here. Say hi to Junior to get started!")
        else:
            # Render up to 8 logs to show a nice scrolling timeline
            for log in state["logs"][:8]:
                render_log(log)
                
    time.sleep(0.5)