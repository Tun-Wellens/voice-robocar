import os
import requests
from dotenv import load_dotenv

load_dotenv()

def get_weather_forecast(lat, lon):
    """
    Retrieves the current weather conditions and a daily forecast summary 
    for a specific geographic location using the WeatherAPI.

    Args:
        lat (float): The latitude of the location.
        lon (float): The longitude of the location.

    Returns:
        str: A formatted string containing the current weather, today's forecast,
             and an hourly summary, or an error message if the API request fails.
    """
    api_key = os.environ.get("WEATHER_API_KEY")
    if not api_key or api_key == "your_weatherapi_key_here":
        return "Weather API key not found or not configured."

    # Utilize the forecast endpoint constrained to 1 day to efficiently 
    # retrieve both the current conditions and the current day's overall forecast.
    url = "http://api.weatherapi.com/v1/forecast.json"
    params = {
        "key": api_key,
        "q": f"{lat},{lon}",
        "days": 1,  # Restrict response strictly to the current day
        "aqi": "no",
        "alerts": "no"
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        current = data.get("current", {})
        condition = current.get("condition", {}).get("text", "Unknown status")
        temp_c = current.get("temp_c", "Unknown")
        
        forecast = data.get("forecast", {}).get("forecastday", [])
        if forecast:
            day = forecast[0].get("day", {})
            max_c = day.get("maxtemp_c", "Unknown")
            min_c = day.get("mintemp_c", "Unknown")
            day_condition = day.get("condition", {}).get("text", "Unknown forecast")
            
            # Extract point-in-time forecast summaries for morning, afternoon, and evening
            hourly_summary = ""
            hours = forecast[0].get("hour", [])
            if len(hours) >= 24:
                morning = hours[9].get("condition", {}).get("text", "")     # 09:00 target
                afternoon = hours[15].get("condition", {}).get("text", "")  # 15:00 target
                evening = hours[20].get("condition", {}).get("text", "")    # 20:00 target
                hourly_summary = f" (Morning: {morning}, Afternoon: {afternoon}, Evening: {evening})"

            return f"Currently {condition} and {temp_c}°C. Today's overall forecast is {day_condition} with a high of {max_c}°C and low of {min_c}°C.{hourly_summary}"
        else:
            return f"Currently {condition} and {temp_c}°C."
            
    except Exception as e:
        return f"Error connecting to Weather API: {e}"
