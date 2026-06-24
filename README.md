# Junior Voice-Robocar

This repository contains the software stack for integrating a context-aware Luxembourgish Voice Assistant into **Junior**, the 360Lab's physical autonomous research vehicle.

The repository includes:
- **Voice Assistant:** The core LLM-based agent processing speech and executing vehicle commands.
- **Dashboard:** A real-time Streamlit web app displaying live car telemetry and the chat/action timeline.
- **Simulation:** CARLA simulator integration nodes to test the voice assistant in a virtual 3D environment.

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
```
**3. Build the Docker Image**
Build the container using Docker Compose:
```bash
docker compose -f docker/docker-compose.yml build
```

---

## Running the Assistant

**1. Start the Voice Assistant**
To start the voice assistant with full access to your host's microphone, speakers, and ROS 2 network, run:

```bash
docker compose -f docker/docker-compose.yml run --rm voice-assistant
```

**2. Start the Live Dashboard**
To view the live tracking map and junior's response timeline, open a new terminal and run:
```bash
cd dashboard
streamlit run app.py
```

**3. Run CARLA Simulation**
If you want to connect the voice assistant to a virtual CARLA environment refer to the step-by-step guide inside `simulation/README.md`.

---

## References

* **KITT Project:** S. Jafarnejad, A. Berthe-Pardo, and R. Frank, Towards a Conversational LLM-based Voice Assistant for Transportation Applications.
* **RoboCar Platform:** M. Testouri, G. Elghazaly, and R. Frank, RoboCar: A Rapidly Deployable Open-Source Platform for Autonomous Driving Research.
