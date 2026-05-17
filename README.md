# Junior Voice-Robocar

This repository contains the software stack for integrating a context-aware Luxembourgish Voice Assistant into **Junior**, the 360Lab's physical autonomous research vehicle.

## Prerequisites

1. **Docker & Docker Compose:** Ensure you have Docker installed on your host machine.
2. **Audio Hardware:** A working microphone and speaker connected to the host machine.
3. **API Keys:** You will need an API key for Google Gemini and TomTom.

---

## Setup & Installation

**1. Clone the repository**
```bash
git clone git@github.com:Tun-Wellens/voice-robocar.git
cd voice-robocar
```

**2. Configure Environment Variables**
Copy the template environment file and add your API keys:
```bash
cp .env.example .env
nano .env

**3. Build the Docker Image**
Build the container using Docker Compose:
```bash
docker compose -f docker/docker-compose.yml build
```

---

## Running the Assistant

To start the voice assistant with full access to your host's microphone, speakers, and ROS 2 network, run:

```bash
docker compose -f docker/docker-compose.yml run --rm voice-assistant
```

---

## Testing with Mock Data (CLI)

Since the assistant relies on LLM function calling to answer questions about the car's state, you can mock the real vehicle's behavior by publishing data directly to the local ROS 2 network.

Open a **new terminal** and use `docker exec` to enter the running container, then use the following commands to simulate the car's sensors:

### Mocking the Current Location (GNSS)

```bash
ros2 topic pub /robocar/gnss robocar_msgs/msg/GNSS "{lat: 49.626, lon: 6.159, altitude: 300.0}"
```

---

## References

* **KITT Project:** S. Jafarnejad, A. Berthe-Pardo, and R. Frank, Towards a Conversational LLM-based Voice Assistant for Transportation Applications.
* **RoboCar Platform:** M. Testouri, G. Elghazaly, and R. Frank, RoboCar: A Rapidly Deployable Open-Source Platform for Autonomous Driving Research.
