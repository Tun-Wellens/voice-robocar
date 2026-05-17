import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from .tomtom_api import reverse_geocode

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
            )
        ]
    )
]

class GeminiAssistant:
    def __init__(self):
        self.client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
        self.model = "gemini-3-flash-preview"
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
            
            # Return the tool execution results to generate the final natural language response
            response = self.chat.send_message(
                types.Part.from_function_response(
                    name=func_name,
                    response={"result": tool_result}
                )
            )
            
        return response.text