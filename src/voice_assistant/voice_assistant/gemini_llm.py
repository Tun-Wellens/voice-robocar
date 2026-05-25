import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from .tomtom_api import reverse_geocode, search_nearby_poi
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
                description="Searches for nearby points of interest (POIs) like restaurants, gas stations, hospitals, etc.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="The type of place to search for, e.g., 'restaurant', 'gas station'."
                        )
                    },
                    required=["query"]
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
        self.chat = self.client.chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction="You are Junior, a context-aware Luxembourgish voice assistant inside an autonomous vehicle. Always respond in Luxembourgish.",
                tools=vehicle_tools,
            )
        )

    def process_prompt(self, text, ros_node):
        response = self.chat.send_message(text)
        
        # Handle function calls triggered by the model
        if response.function_calls:
            function_call = response.function_calls[0]
            func_name = function_call.name
            
            # Execute the requested tool and retrieve state from the ROS 2 node
            tool_result = {}
            if func_name == "get_current_location":
                if ros_node.current_gnss is not None:
                    lat = ros_node.current_gnss.lat
                    lon = ros_node.current_gnss.lon
                    address = reverse_geocode(lat, lon)
                    tool_result = {
                        "latitude": lat, 
                        "longitude": lon,
                        "address": address
                    }
                else:
                    tool_result = {"error": "GPS signal lost or not yet received."}
            elif func_name == "get_destination":
                # TODO: Replace placeholder with actual path parsing logic
                tool_result = {"destination_info": "We are routing to Kirchberg Campus."} 
            elif func_name == "search_nearby_poi":
                if ros_node.current_gnss is not None:
                    # In newer google-genai, args might be accessed as attribute or dict
                    query = getattr(function_call.args, "query", "") if hasattr(function_call.args, "query") else function_call.args.get("query", "")
                    lat = ros_node.current_gnss.lat
                    lon = ros_node.current_gnss.lon
                    poi_results = search_nearby_poi(query, lat, lon)
                    tool_result = {"pois": poi_results, "query": query}
                else:
                    tool_result = {"error": "GPS signal lost or not yet received. Cannot search for nearby POIs."}
            elif func_name == "get_weather_forecast":
                if ros_node.current_gnss is not None:
                    lat = ros_node.current_gnss.lat
                    lon = ros_node.current_gnss.lon
                    weather_result = get_weather_forecast(lat, lon)
                    tool_result = {"weather": weather_result}
                else:
                    tool_result = {"error": "GPS signal lost or not yet received. Cannot fetch weather."}
            
            # Return the tool execution results to generate the final natural language response
            response = self.chat.send_message(
                types.Part.from_function_response(
                    name=func_name,
                    response={"result": tool_result}
                )
            )
            
        return response.text