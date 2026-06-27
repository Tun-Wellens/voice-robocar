import os
import sys
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from std_msgs.msg import String

from .poi_api import reverse_geocode, search_nearby_poi
from .weather_api import get_weather_forecast

load_dotenv()

# Define available tools for the GenAI client
vehicle_tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_current_location",
                description="Retrieves the current GPS location (latitude and longitude) and human-readable address of the autonomous vehicle.",
            ),
            types.FunctionDeclaration(
                name="get_destination",
                description="Retrieves the final destination the autonomous vehicle is currently routing to.",
            ),
            types.FunctionDeclaration(
                name="search_nearby_poi",
                description="Searches for nearby points of interest (POIs) like restaurants, cinemas, gas stations, etc. Returns their GPS coordinates.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="The type of place to search for, e.g., 'Kinepolis', 'restaurant'."
                        )
                    },
                    required=["query"]
                )
            ),
            types.FunctionDeclaration(
                name="start_navigation",
                description="Starts the autopilot to drive the car to a specific GPS coordinate. Requires search_nearby_poi to be called first to find the exact latitude and longitude.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "latitude": types.Schema(type="NUMBER", description="Destination latitude"),
                        "longitude": types.Schema(type="NUMBER", description="Destination longitude"),
                        "destination_name": types.Schema(type="STRING", description="Name of the destination")
                    },
                    required=["latitude", "longitude", "destination_name"]
                )
            ),
            types.FunctionDeclaration(
                name="get_weather_forecast",
                description="Retrieves the current weather and daily forecast for the vehicle's current location.",
            ),
            types.FunctionDeclaration(
                name="turn_on_headlights",
                description="Turns on the vehicle's headlights.",
            ),
            types.FunctionDeclaration(
                name="turn_on_hazard_lights",
                description="Turns on the vehicle's hazard lights (warning blinkers).",
            ),
            types.FunctionDeclaration(
                name="turn_off_headlights",
                description="Turns off the vehicle's headlights.",
            ),
            types.FunctionDeclaration(
                name="turn_off_hazard_lights",
                description="Turns off the vehicle's hazard lights (warning blinkers).",
            ),
            types.FunctionDeclaration(
                name="turn_on_interior_light",
                description="Turns on the vehicle's interior cabin light.",
            ),
            types.FunctionDeclaration(
                name="turn_off_interior_light",
                description="Turns off the vehicle's interior cabin light.",
            ),
            types.FunctionDeclaration(
                name="open_doors",
                description="Opens all doors of the vehicle.",
            ),
            types.FunctionDeclaration(
                name="close_doors",
                description="Closes all doors of the vehicle.",
            )
        ]
    )
]

class GeminiAssistant:
    def __init__(self):
        self.client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
        self.model = "gemini-2.5-flash"
        self.log_publisher = None
        self.nav_publisher = None
        self.cmd_publisher = None
        
        # --- OPTIMIZED INSTRUCTION PROMPT ---
        instruction = (
            "You are Junior, a context-aware Luxembourgish voice assistant inside an autonomous vehicle. "
            "Always respond in Luxembourgish.\n\n"
            "Routing & Navigation:\n"
            "- When asked to drive somewhere, always call 'search_nearby_poi' first to find the coordinates.\n"
            "- The POI search API works best with standard terms (English/French). If someone asks for a generic place "
            "in Luxembourgish (like 'Apdikt' or 'Spidol'), translate the query term to English or French (like 'pharmacy' or 'hospital'). "
            "If they ask for a specific brand name or exact location, keep it exactly as spoken.\n"
            "- If the first search returns no results, try again with a different synonym before giving up.\n"
            "- CRITICAL RULE: If the search returns a valid POI, DO NOT ask the user for confirmation! "
            "You must IMMEDIATELY call 'start_navigation' to start driving there. Only after you call "
            "'start_navigation' should you generate your spoken response confirming that the car is on its way.\n\n"
            "Vehicle Commands:\n"
            "- You can control the car's lights and doors using the provided tools.\n\n"
            "Always confirm what you've done to the user in a friendly way (e.g., confirming autopilot has started or lights are on)."
        )
        
        self.chat = self.client.chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                tools=vehicle_tools,
            )
        )

    def _send_message_with_retry(self, message, max_retries=3, delay=5):
        for attempt in range(max_retries):
            try:
                return self.chat.send_message(message)
            except Exception as e:
                # Retry if we hit a 503 unavailability error
                if '503' in str(e) and attempt < max_retries - 1:
                    print(f"System: Model unavailable (503). Retrying in {delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                else:
                    raise

    def process_prompt(self, text, ros_node):
        # Initialize ROS 2 publisher for UI logging if not already created
        if ros_node is not None:
            if self.log_publisher is None:
                self.log_publisher = ros_node.create_publisher(String, '/assistant/logs', 10)
            if self.nav_publisher is None:
                self.nav_publisher = ros_node.create_publisher(String, '/assistant/navigation_goal', 10)
            if self.cmd_publisher is None:
                self.cmd_publisher = ros_node.create_publisher(String, '/assistant/vehicle_commands', 10)

        response = self._send_message_with_retry(text)
        
        # Process any tool calls requested by the model
        while response and getattr(response, 'function_calls', None):
            function_responses = []
            
            # Execute requested tools
            for function_call in response.function_calls:
                func_name = function_call.name
                
                # Safely extract arguments
                args = function_call.args if hasattr(function_call, "args") else {}
                if not isinstance(args, dict):
                    args = {k: getattr(args, k) for k in dir(args) if not k.startswith('_')}
                    
                print(f"System: Executing tool '{func_name}' with args: {args}")
                
                tool_result = {}
                if func_name == "get_current_location":
                    if ros_node.current_gnss is not None:
                        lat = ros_node.current_gnss.lat
                        lon = ros_node.current_gnss.lon
                        address = reverse_geocode(lat, lon)
                        tool_result = {"latitude": lat, "longitude": lon, "address": address}
                    else:
                        tool_result = {"error": "GPS signal lost or not yet received."}
                        
                elif func_name == "get_destination":
                    tool_result = {"destination_info": "We are routing to Kirchberg Campus."} 
                    
                elif func_name == "search_nearby_poi":
                    query = args.get("query", "")
                    if ros_node.current_gnss is not None:
                        lat = ros_node.current_gnss.lat
                        lon = ros_node.current_gnss.lon
                        poi_results = search_nearby_poi(query, lat, lon)
                        tool_result = {"pois": poi_results, "query": query}
                    else:
                        tool_result = {"error": "GPS signal lost. Cannot search for POIs."}
                        
                elif func_name == "start_navigation":
                    target_lat = args.get("latitude")
                    target_lon = args.get("longitude")
                    dest_name = args.get("destination_name")
                    
                    if target_lat and target_lon:
                        print(f"System: Requesting vehicle to route to {dest_name}...")
                        
                        # publish the navigation goal to the ROS 2 topic for the CARLA Navigator Node
                        if self.nav_publisher is not None:
                            goal_msg = String()
                            goal_msg.data = json.dumps({
                                "latitude": target_lat,
                                "longitude": target_lon,
                                "destination_name": dest_name
                            })
                            self.nav_publisher.publish(goal_msg)
                            tool_result = {"status": "success", "message": f"Navigation coordinates broadcasted for {dest_name}."}
                        else:
                            tool_result = {"error": "ROS 2 publisher not initialized."}
                    else:
                        tool_result = {"error": "Invalid GPS coordinates provided."}
                        
                elif func_name == "get_weather_forecast":
                    if ros_node.current_gnss is not None:
                        lat = ros_node.current_gnss.lat
                        lon = ros_node.current_gnss.lon
                        weather_result = get_weather_forecast(lat, lon)
                        tool_result = {"weather": weather_result}
                    else:
                        tool_result = {"error": "GPS signal lost. Cannot fetch weather."}
                        
                elif func_name == "turn_on_headlights":
                    if self.cmd_publisher is not None:
                        cmd_msg = String()
                        cmd_msg.data = json.dumps({"command": "headlights_on"})
                        self.cmd_publisher.publish(cmd_msg)
                        tool_result = {"status": "success", "message": "Headlights turned on."}
                    else:
                        tool_result = {"error": "ROS 2 publisher not initialized."}
                        
                elif func_name == "turn_on_hazard_lights":
                    if self.cmd_publisher is not None:
                        cmd_msg = String()
                        cmd_msg.data = json.dumps({"command": "hazards_on"})
                        self.cmd_publisher.publish(cmd_msg)
                        tool_result = {"status": "success", "message": "Hazard lights turned on."}
                    else:
                        tool_result = {"error": "ROS 2 publisher not initialized."}

                elif func_name == "turn_off_headlights":
                    if self.cmd_publisher is not None:
                        cmd_msg = String()
                        cmd_msg.data = json.dumps({"command": "headlights_off"})
                        self.cmd_publisher.publish(cmd_msg)
                        tool_result = {"status": "success", "message": "Headlights turned off."}
                    else:
                        tool_result = {"error": "ROS 2 publisher not initialized."}

                elif func_name == "turn_off_hazard_lights":
                    if self.cmd_publisher is not None:
                        cmd_msg = String()
                        cmd_msg.data = json.dumps({"command": "hazards_off"})
                        self.cmd_publisher.publish(cmd_msg)
                        tool_result = {"status": "success", "message": "Hazard lights turned off."}
                    else:
                        tool_result = {"error": "ROS 2 publisher not initialized."}

                elif func_name == "turn_on_interior_light":
                    if self.cmd_publisher is not None:
                        cmd_msg = String()
                        cmd_msg.data = json.dumps({"command": "interior_on"})
                        self.cmd_publisher.publish(cmd_msg)
                        tool_result = {"status": "success", "message": "Interior lights turned on."}
                    else:
                        tool_result = {"error": "ROS 2 publisher not initialized."}
                        
                elif func_name == "turn_off_interior_light":
                    if self.cmd_publisher is not None:
                        cmd_msg = String()
                        cmd_msg.data = json.dumps({"command": "interior_off"})
                        self.cmd_publisher.publish(cmd_msg)
                        tool_result = {"status": "success", "message": "Interior lights turned off."}
                    else:
                        tool_result = {"error": "ROS 2 publisher not initialized."}

                elif func_name == "open_doors":
                    if self.cmd_publisher is not None:
                        cmd_msg = String()
                        cmd_msg.data = json.dumps({"command": "open_doors"})
                        self.cmd_publisher.publish(cmd_msg)
                        tool_result = {"status": "success", "message": "Doors opened."}
                    else:
                        tool_result = {"error": "ROS 2 publisher not initialized."}

                elif func_name == "close_doors":
                    if self.cmd_publisher is not None:
                        cmd_msg = String()
                        cmd_msg.data = json.dumps({"command": "close_doors"})
                        self.cmd_publisher.publish(cmd_msg)
                        tool_result = {"status": "success", "message": "Doors closed."}
                    else:
                        tool_result = {"error": "ROS 2 publisher not initialized."}
                
                # Publish log data to ROS 2 for the Streamlit dashboard
                if self.log_publisher is not None:
                    log_data = {
                        "action": func_name,
                        "arguments": args,
                        "result": tool_result
                    }
                    msg = String()
                    msg.data = json.dumps(log_data)
                    self.log_publisher.publish(msg)

                # Map result to the format expected by the model
                function_responses.append(
                    types.Part.from_function_response(
                        name=func_name,
                        response={"result": tool_result}
                    )
                )

            response = self._send_message_with_retry(function_responses)

        # Extract final text or fallback to default error
        final_text = getattr(response, "text", "Entschëllegt, et gouf e Problem beim Kommunizéieren.") if response else "Entschëllegt."

        # Publish the final response text to the UI
        if self.log_publisher is not None and final_text:
            log_data = {
                "type": "response",
                "text": final_text
            }
            msg = String()
            msg.data = json.dumps(log_data)
            self.log_publisher.publish(msg)
            
        return final_text