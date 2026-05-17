import os
import requests
from dotenv import load_dotenv

load_dotenv()

def reverse_geocode(lat, lon):
    """
    Converts latitude and longitude into a human-readable address 
    using the TomTom Reverse Geocoding API.
    """
    api_key = os.environ.get("TOMTOM_API_KEY")
    if not api_key:
        return "TomTom API key not found."

    url = f"https://api.tomtom.com/search/2/reverseGeocode/{lat},{lon}.json"
    params = {
        "key": api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data.get("addresses") and len(data["addresses"]) > 0:
            address_info = data["addresses"][0]["address"]
            return address_info.get("freeformAddress", "Unknown Address")
        return "Location not found."
    except Exception as e:
        return f"Error connecting to TomTom API: {e}"
