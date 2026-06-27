import os
import requests
import math
from dotenv import load_dotenv

load_dotenv()

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates the straight-line distance between two GPS points in meters."""
    R = 6371000  # Radius of the Earth in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def reverse_geocode(lat, lon):
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key: return "Google Maps API key not found."

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"latlng": f"{lat},{lon}", "key": api_key}
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get("results"):
            return data["results"][0].get("formatted_address", "Unknown Address")
        return "Location not found."
    except Exception as e:
        return f"Error: {e}"

def search_nearby_poi(query, lat, lon, radius=2000, limit=5):
    """
    Searches using Google Places API (New).
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key: return "Google Maps API key not found."

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName.text,places.formattedAddress,places.location"
    }
    
    payload = {
        "textQuery": query,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": float(radius)
            }
        },
        "maxResultCount": 10 
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        
        if response.status_code != 200:
            print(f"Google API Error: {response.text}")
            
        response.raise_for_status()
        data = response.json()
        
        places = data.get("places", [])
        if not places: 
            return []
            
        pois = []
        for p in places:
            p_lat = p.get("location", {}).get("latitude")
            p_lon = p.get("location", {}).get("longitude")
            
            # Calculate distance
            dist = haversine_distance(lat, lon, p_lat, p_lon) if p_lat and p_lon else 0
            
            pois.append({
                "name": p.get("displayName", {}).get("text", "Unknown Name"),
                "address": p.get("formattedAddress", "Unknown Address"),
                "distance_meters": round(dist),
                "latitude": p_lat,
                "longitude": p_lon
            })
            
        pois.sort(key=lambda x: x["distance_meters"])
        
        return pois[:limit]
        
    except Exception as e:
        return f"Error connecting to Google Places API: {e}"