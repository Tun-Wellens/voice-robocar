import carla
import pygame
import sys
import numpy as np
import pyproj
import xml.etree.ElementTree as ET

class RenderObject:
    def __init__(self): self.surface = None

def camera_callback(image, render_object):
    array = np.frombuffer(image.raw_data, dtype=np.dtype("uint8"))
    array = np.reshape(array, (image.height, image.width, 4))
    array = array[:, :, :3][:, :, ::-1]
    render_object.surface = pygame.surfarray.make_surface(array.swapaxes(0, 1))

def main():
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
    car_bp = world.get_blueprint_library().filter('vehicle.tesla.model3')[0]
    car_bp.set_attribute('role_name', 'ego_vehicle') 
    
    vehicle = world.try_spawn_actor(car_bp, spawn_points[0])
    if not vehicle: return

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
                vehicle.apply_control(control)

            if render_obj.surface is not None:
                display.blit(render_obj.surface, (0, 0))

            loc = vehicle.get_location()
            
            merc_x = loc.x
            merc_y = -loc.y 
            true_lon, true_lat = map_projection(merc_x, merc_y, inverse=True)

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
        print("Cleaning up...")
        camera.destroy()
        vehicle.destroy()
        pygame.quit()

if __name__ == '__main__':
    main()