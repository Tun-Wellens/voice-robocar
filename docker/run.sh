#!/bin/bash
set -e

# Source the base ROS 2 environment
source /opt/ros/jazzy/setup.bash

# Source the local workspace overlay to make custom packages available
if [ -f /workspace/ros2_ws/install/setup.bash ]; then
    source /workspace/ros2_ws/install/setup.bash
fi

echo "ROS 2 Jazzy environment sourced. Starting Voice Assistant Node..."

# Execute the provided container command, or default to the main node
if [ $# -eq 0 ]; then
    exec ros2 run voice_assistant main_node
else
    exec "$@"
fi