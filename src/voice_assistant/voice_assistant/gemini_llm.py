import os
import sys
import threading
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from std_msgs.msg import String

from .tomtom_api import reverse_geocode, search_nearby_poi
from .weather_api import get_weather_forecast

# Ensure the simulation directory is accessible for the navigation module
current_dir = os.path.dirname(os.path.abspath(__file__))
simulation_dir = os.path.abspath(os.path.join(current_dir, "../../../simulation"))
if simulation_dir not in sys.path:
    sys.path.append(simulation_dir)

from navigate_to_point import navigate_to_gnss

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
            )
        ]
    )
]

class GeminiAssistant:
    def __init__(self):
        self.client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
        self.model = "gemini-3.5-flash"
        self.log_publisher = None
        
        instruction = (
            "You are Junior, a context-aware Luxembourgish voice assistant inside an autonomous vehicle. "
            "Always respond in Luxembourgish. "
            "If the user asks to drive to a specific place, you must first call 'search_nearby_poi' "
            "to find its coordinates, and then immediately call 'start_navigation' using those coordinates. "
            "Confirm to the user once autopilot is engaged."
        )
        
        self.chat = self.client.chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                tools=vehicle_tools,
            )
        )

    def process_prompt(self, text, ros_node):
        # Initialize ROS 2 publisher for UI logging if not already created
        if self.log_publisher is None and ros_node is not None:
            self.log_publisher = ros_node.create_publisher(String, '/assistant/logs', 10)

        response = self.chat.send_message(text)
        
        while response.function_calls:
            function_call = response.function_calls[0]
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
                    print(f"System: Engaging autopilot to {dest_name} (Lat: {target_lat:.6f}, Lon: {target_lon:.6f}).")
                    nav_thread = threading.Thread(
                        target=navigate_to_gnss, 
                        args=(target_lat, target_lon),
                        daemon=True
                    )
                    nav_thread.start()
                    tool_result = {"status": "success", "message": f"Autopilot engaged for {dest_name}."}
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

            # Send the tool result back to Gemini
            response = self.chat.send_message(
                types.Part.from_function_response(
                    name=func_name,
                    response={"result": tool_result}
                )
            )
            
        return response.text