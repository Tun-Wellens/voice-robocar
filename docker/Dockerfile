# Use the multi-arch ROS 2 Jazzy base image (Ubuntu 24.04 Noble)
FROM ros:jazzy-ros-base

# Set the working directory
WORKDIR /workspace/ros2_ws

# 1. Install system dependencies for Audio and Python
# - libasound2-dev, alsa-utils, libportaudio2 are required for recording/playing sound
RUN apt-get update && apt-get install -y \
    python3-pip \
    libasound2-dev \
    alsa-utils \
    libportaudio2 \
    pulseaudio \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 2. Copy the Python requirements and install them
COPY requirements.txt /workspace/
RUN pip3 install --no-cache-dir --break-system-packages -r /workspace/requirements.txt

# 3. Copy the ROS 2 source code
COPY src/ /workspace/ros2_ws/src/

# 4. Build the ROS 2 workspace for Jazzy
RUN /bin/bash -c "source /opt/ros/jazzy/setup.bash && colcon build --symlink-install"

# 5. Copy the entrypoint script and make it executable
COPY docker/run.sh /workspace/run.sh
RUN chmod +x /workspace/run.sh

# 6. Set the entrypoint
ENTRYPOINT ["/workspace/run.sh"]