import carla
import pygame
import sys
import numpy as np
import pyproj
import xml.etree.ElementTree as ET
import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import Header, String

from robocar_msgs.msg import GNSS

class CustomGnssPublisher(Node):
    def __init__(self):
        super().__init__('custom_gnss_publisher')
        self.pub = self.create_publisher(GNSS, '/sensors/gnss', 10)
        self.cmd_sub = self.create_subscription(String, '/assistant/vehicle_commands', self.cmd_callback, 10)
        self.pending_command = None
        
    def cmd_callback(self, msg):
        try:
            data = json.loads(msg.data)
            self.pending_command = data.get("command")
        except:
            pass
        
    def publish_data(self, lat, lon, transform, vel, accel, ang_vel):
        msg = GNSS()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "ego_vehicle"
        
        # Position
        msg.lat = float(lat)
        msg.lon = float(lon)
        msg.altitude = float(transform.location.z)
        
        # Orientation
        msg.roll = float(transform.rotation.roll)
        msg.pitch = float(transform.rotation.pitch)
        msg.heading = float(transform.rotation.yaw)
        
        # Velocity (CARLA is in m/s)
        msg.velocity_north = float(-vel.y) # In CARLA, +Y is South, so -Y is North
        msg.velocity_east = float(vel.x)   # In CARLA, +X is East
        msg.velocity_down = float(-vel.z)  # In CARLA, +Z is Up
        msg.velocity = float(np.sqrt(vel.x**2 + vel.y**2 + vel.z**2))
        
        # Angular Rate (CARLA gives deg/s)
        msg.angular_rate_x = float(ang_vel.x)
        msg.angular_rate_y = float(ang_vel.y)
        msg.angular_rate_z = float(ang_vel.z)
        
        # Acceleration (CARLA is in m/s^2)
        msg.accel_x = float(accel.x)
        msg.accel_y = float(accel.y)
        msg.accel_z = float(accel.z)
        
        # Sigma (Dummy values since simulation is perfect)
        msg.sigma_x = 0.01
        msg.sigma_y = 0.01
        
        self.pub.publish(msg)

class RenderObject:
    def __init__(self): self.surface = None

def camera_callback(image, render_object):
    array = np.frombuffer(image.raw_data, dtype=np.dtype("uint8"))
    array = np.reshape(array, (image.height, image.width, 4))
    array = array[:, :, :3][:, :, ::-1]
    render_object.surface = pygame.surfarray.make_surface(array.swapaxes(0, 1))

def main():
    
    rclpy.init()
    ros_node = CustomGnssPublisher()

    pygame.init()
    pygame.font.init()
    display = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("CARLA Ego Vehicle Viewer")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont('mono', 20, bold=True)

    client = carla.Client('127.0.0.1', 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    carla_map = world.get_map()
    
    xodr = carla_map.to_opendrive()
    root = ET.fromstring(xodr.encode('utf-8'))
    geo_ref = root.find('.//geoReference').text.replace("<![CDATA[", "").replace("]]>", "").strip()
    map_projection = pyproj.Proj(geo_ref)

    # Spawn vehicle
    spawn_points = carla_map.get_spawn_points()
    car_bp = world.get_blueprint_library().filter('vehicle.lincoln.mkz_2020')[0]
    car_bp.set_attribute('role_name', 'ego_vehicle') 
    
    vehicle = world.try_spawn_actor(car_bp, spawn_points[0])
    if not vehicle: 
        print("Error: Could not spawn vehicle!")
        return

    cam_bp = world.get_blueprint_library().find('sensor.camera.rgb')
    cam_bp.set_attribute('image_size_x', '800')
    cam_bp.set_attribute('image_size_y', '600')
    camera = world.spawn_actor(cam_bp, carla.Transform(carla.Location(x=-5.5, z=2.5), carla.Rotation(pitch=-8.0)), attach_to=vehicle)
    render_obj = RenderObject()
    camera.listen(lambda image: camera_callback(image, render_obj))

    try:
        while True:
            clock.tick(60)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT: return

            # Manual Control
            keys = pygame.key.get_pressed()
            if keys[pygame.K_w] or keys[pygame.K_s] or keys[pygame.K_a] or keys[pygame.K_d] or keys[pygame.K_SPACE]:
                control = carla.VehicleControl()
                control.throttle = 1.0 if keys[pygame.K_w] else 0.0
                control.brake = 1.0 if keys[pygame.K_s] else 0.0
                control.steer = 0.0
                if keys[pygame.K_a]: control.steer = -0.8
                if keys[pygame.K_d]: control.steer = 0.8
                control.reverse = keys[pygame.K_s] and vehicle.get_velocity().length() < 0.1
                control.hand_brake = keys[pygame.K_SPACE]
                vehicle.apply_control(control)

            # Check for incoming commands from the Voice Assistant
            if ros_node.pending_command:
                cmd = ros_node.pending_command
                current_lights = vehicle.get_light_state()
                
                if cmd == "headlights_on":
                    vehicle.set_light_state(carla.VehicleLightState(current_lights | carla.VehicleLightState.Position | carla.VehicleLightState.LowBeam))
                elif cmd == "headlights_off":
                    vehicle.set_light_state(carla.VehicleLightState(current_lights & ~carla.VehicleLightState.Position & ~carla.VehicleLightState.LowBeam))
                elif cmd == "hazards_on":
                    vehicle.set_light_state(carla.VehicleLightState(current_lights | carla.VehicleLightState.LeftBlinker | carla.VehicleLightState.RightBlinker))
                elif cmd == "hazards_off":
                    vehicle.set_light_state(carla.VehicleLightState(current_lights & ~carla.VehicleLightState.LeftBlinker & ~carla.VehicleLightState.RightBlinker))
                elif cmd == "interior_on":
                    vehicle.set_light_state(carla.VehicleLightState(current_lights | carla.VehicleLightState.Interior))
                elif cmd == "interior_off":
                    vehicle.set_light_state(carla.VehicleLightState(current_lights & ~carla.VehicleLightState.Interior))
                elif cmd == "open_doors":
                    vehicle.open_door(carla.VehicleDoor.All)
                elif cmd == "close_doors":
                    vehicle.close_door(carla.VehicleDoor.All)
                    
                ros_node.pending_command = None

            if render_obj.surface is not None:
                display.blit(render_obj.surface, (0, 0))

            loc = vehicle.get_location()
            
            merc_x = loc.x
            merc_y = -loc.y 
            true_lon, true_lat = map_projection(merc_x, merc_y, inverse=True)

            transform = vehicle.get_transform()
            vel = vehicle.get_velocity()
            accel = vehicle.get_acceleration()
            ang_vel = vehicle.get_angular_velocity()
            
            # PUBLISH TO ROS 2 
            ros_node.publish_data(true_lat, true_lon, transform, vel, accel, ang_vel)
            rclpy.spin_once(ros_node, timeout_sec=0)

            # RENDER HUD 
            hud_lines = [
                f" LOC:  x={loc.x:7.1f}, y={loc.y:7.1f}, z={loc.z:5.1f} ",
                f" GNSS: Lat {true_lat:.6f}, Lon {true_lon:.6f} " 
            ]
            
            y_offset = 10
            for line in hud_lines:
                text_surface = font.render(line, True, (255, 255, 255))
                text_rect = text_surface.get_rect(topleft=(10, y_offset))
                pygame.draw.rect(display, (0, 0, 0), text_rect)
                display.blit(text_surface, text_rect)
                y_offset += 30 

            pygame.display.flip()

    finally:
        print("\nCleaning up...")
        camera.destroy()
        vehicle.destroy()
        pygame.quit()
        
        # Safely shut down ROS 2 node
        ros_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()