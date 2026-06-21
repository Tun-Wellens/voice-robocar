import carla
import sys
import os
import heapq
import pyproj
import xml.etree.ElementTree as ET

carla_api_path = '/home/owner/carla-source/PythonAPI/carla'
sys.path.append(carla_api_path)

from agents.navigation.basic_agent import BasicAgent
from agents.navigation.local_planner import RoadOption

def build_custom_astar_path(start_wp, end_loc, world):
    counter = 0
    queue = []
    heapq.heappush(queue, (0, 0, counter, start_wp, [(start_wp, RoadOption.LANEFOLLOW)]))
    visited_ids = set()
    closest_dist = start_wp.transform.location.distance(end_loc)
    best_partial_path = []
    nodes_explored = 0

    while queue:
        f_score, g_score, _, current_wp, path = heapq.heappop(queue)
        wp_hash = current_wp.id
        
        if wp_hash in visited_ids: continue
        visited_ids.add(wp_hash)
        nodes_explored += 1
        
        dist_to_goal = current_wp.transform.location.distance(end_loc)
        if dist_to_goal < closest_dist:
            closest_dist = dist_to_goal
            best_partial_path = path

        if dist_to_goal < 5.0:
            for p, _ in path:
                world.debug.draw_point(p.transform.location, size=0.15, color=carla.Color(0,0,255), life_time=0.0)
            return path
            
        next_wps = current_wp.next(2.0)
        
        for next_wp in next_wps:
            if next_wp.id not in visited_ids:
                new_g = g_score + 2.0
                h = next_wp.transform.location.distance(end_loc)
                new_f = new_g + h
                counter += 1
                new_path = list(path)
                new_path.append((next_wp, RoadOption.LANEFOLLOW))
                heapq.heappush(queue, (new_f, new_g, counter, next_wp, new_path))
                
        if nodes_explored > 50000: break

    print(f"Warning: True destination unreachable. Driving as close as possible ({closest_dist:.1f}m away)")
    return best_partial_path


def navigate_to(target_x, target_y):
    """
    Commands the existing ego_vehicle to drive to a specific x, y coordinate.
    """
    client = carla.Client('127.0.0.1', 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    carla_map = world.get_map()

    vehicles = world.get_actors().filter('vehicle.*')
    ego_vehicle = next((v for v in vehicles if v.attributes.get('role_name') == 'ego_vehicle'), None)
    
    if not ego_vehicle:
        print("ERROR: Could not find 'ego_vehicle'!")
        return False

    print(f"\nRemote command received! Navigating to: ({target_x}, {target_y})")
    
    start_loc = ego_vehicle.get_location()
    start_wp = carla_map.get_waypoint(start_loc, project_to_road=True, lane_type=carla.LaneType.Driving)
    
    end_loc = carla.Location(x=target_x, y=target_y, z=0.0)
    end_loc_vis = carla.Location(x=end_loc.x, y=end_loc.y, z=2.0)
    world.debug.draw_point(end_loc_vis, size=0.5, color=carla.Color(255, 0, 0), life_time=10.0)
    world.debug.draw_string(end_loc_vis, "DESTINATION", draw_shadow=False, color=carla.Color(255, 0, 0), life_time=0.0)

    print("Calculating Custom A* Route...")
    custom_route = build_custom_astar_path(start_wp, end_loc, world)

    agent = BasicAgent(ego_vehicle, target_speed=40)
    agent.get_local_planner().set_global_plan(custom_route)
    
    print(">>> Autopilot Engaged! Press CTRL+C to cancel route.")
    try:
        while True:
            world.wait_for_tick()
            
            if agent.done():
                print("Arrived at destination!")
                ego_vehicle.apply_control(carla.VehicleControl(brake=1.0))
                return True
                
            control = agent.run_step()
            ego_vehicle.apply_control(control)
            
    except KeyboardInterrupt:
        print("\nRoute Cancelled by User.")
        ego_vehicle.apply_control(carla.VehicleControl(brake=1.0))
        return False
    
def navigate_to_gnss(target_lat, target_lon):
    client = carla.Client('127.0.0.1', 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    carla_map = world.get_map()

    xodr = carla_map.to_opendrive()
    root = ET.fromstring(xodr.encode('utf-8'))
    geo_ref = root.find('.//geoReference').text.replace("<![CDATA[", "").replace("]]>", "").strip()

    proj = pyproj.Proj(geo_ref)
    merc_x, merc_y = proj(target_lon, target_lat)

    carla_x = merc_x
    carla_y = -merc_y 

    print(f"\nTarget GNSS: Lat {target_lat:.6f}, Lon {target_lon:.6f}")
    print(f"Calculated CARLA Coordinates: x={carla_x:.1f}, y={carla_y:.1f}")

    return navigate_to(carla_x, carla_y)

if __name__ == '__main__':
    navigate_to(target_x=531.7, target_y=-326.4)