import carla
import os
import xml.etree.ElementTree as ET
import re

os.environ["PROJ_LIB"] = "/usr/share/proj"

print("Parsing OSM XML...")
tree = ET.parse("map.osm")
root = tree.getroot()

bounds = root.find('bounds')
if bounds is not None:
    center_lat = (float(bounds.get('minlat')) + float(bounds.get('maxlat'))) / 2.0
    center_lon = (float(bounds.get('minlon')) + float(bounds.get('maxlon'))) / 2.0
else:
    center_lat = 49.640569
    center_lon = 6.164656

allowed_highways = {
    "motorway", "motorway_link", "trunk", "trunk_link", 
    "primary", "primary_link", "secondary", "secondary_link", 
    "tertiary", "tertiary_link", "unclassified", "residential"
}

ways_removed = 0
for way in root.findall('way'):
    is_drivable = False
    for tag in way.findall('tag'):
        if tag.get('k') == 'highway' and tag.get('v') in allowed_highways:
            is_drivable = True
            
    if not is_drivable:
        root.remove(way)
        ways_removed += 1

print(f"Removed {ways_removed} non-drivable features. Tunnels KEPT.")

osm_data = ET.tostring(root, encoding='utf-8').decode('utf-8')

print("Converting to OpenDRIVE...")
settings = carla.Osm2OdrSettings()
settings.set_osm_way_types(list(allowed_highways))
settings.generate_traffic_lights = True
settings.center_map = False 

proj_str = f"+proj=tmerc +lat_0={center_lat} +lon_0={center_lon} +k=1 +x_0=0 +y_0=0 +datum=WGS84 +ellps=WGS84 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs"
settings.proj_string = proj_str

xodr_data = carla.Osm2Odr.convert(osm_data, settings)
clean_geo = f"<![CDATA[{proj_str}]]>"
xodr_data = re.sub(r'<geoReference>.*?</geoReference>', f'<geoReference>{clean_geo}</geoReference>', xodr_data, flags=re.DOTALL)

with open("my_map.xodr", 'w', encoding='utf-8') as f:
    f.write(xodr_data)
print("Conversion complete!")