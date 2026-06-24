# CARLA Simulation Integration

This directory contains the custom nodes required to bridge the CARLA simulator into the Junior Voice Assistant ecosystem. It allows you to test navigation, vehicle controls (like headlights), and GPS-aware AI responses entirely in a virtual environment.

## Included Map Files

If you want to simulate Junior driving around Kirchberg, you can use the map files provided in this directory:
- **`map.osm`**: The raw OpenStreetMap data of the Kirchberg area.
- **`convert_map.py`**: A utility script used to process and convert the map data.
- **`my_map.xodr`**: The OpenDRIVE format file defining the road network, lanes, and rules.
- **`my_map.fbx`**: The 3D mesh containing the visual representation of the buildings and roads.

**How to use them:** To simulate on this Kirchberg map (or any custom map), you need to compile them into Unreal Engine. Place the `.xodr` and `.fbx` files into CARLA's `Import` folder, then run `make import` in your CARLA root directory. Once imported, you can open the map in the Editor.

## Step-by-Step Testing Guide

First, ensure you have CARLA installed (you can build it from the [official repository](https://github.com/carla-simulator/carla/tree/ue4/0.9.16)).

### 1. Launch the CARLA Editor
Open a terminal and start the Unreal Engine CARLA editor:
```bash
cd ~/carla-source
make launch
```
*Once the Unreal Editor opens, load your custom map and click the **Play** button at the top.*

### 2. Start the ROS 2 Bridge (Terminal 1)
In a new terminal, launch the ROS 2 Bridge in passive mode. This ensures it doesn't freeze the editor and just hooks into the running map.

```bash
source /opt/ros/jazzy/setup.bash
source ~/carla_bridge_ws/install/setup.bash

ros2 launch carla_ros_bridge carla_ros_bridge.launch.py town:='map_package/Maps/my_map/my_map' timeout:=20 passive:=True
```

### 3. Start the Virtual Drive/Dashboard Link (Terminal 2)
In a second terminal, start the `lite_drive.py` script. This handles translating the CARLA sensors into our custom ROS topics (like `/sensors/gnss`) and listens for vehicle commands like headlights.

```bash
source /opt/ros/jazzy/setup.bash
source ~/carla_bridge_ws/install/setup.bash
source ~/BSP-S6/voice-robocar/install/setup.bash

cd ~/BSP-S6/voice-robocar/simulation
python3 lite_drive.py
```

### 4. Start the Navigator Node (Terminal 3)
In a third terminal, launch the node that listens for the Voice Assistant's AI autopilot coordinates and steers the virtual car.

```bash
source /opt/ros/jazzy/setup.bash
source ~/carla_bridge_ws/install/setup.bash
source ~/BSP-S6/voice-robocar/install/setup.bash

cd ~/BSP-S6/voice-robocar/simulation
python3 carla_navigator_node.py
```

---

### 5. Launch the Voice Assistant
With the simulator actively bridging data into ROS 2, you can now start the actual Voice Assistant Docker container (as shown in the main `README.md`). 

Speak into your microphone and test if Junior can turn on the headlights or route you around the virtual map!
