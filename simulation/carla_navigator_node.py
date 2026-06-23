import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import threading

from navigate_to_point import navigate_to_gnss

class CarlaNavigatorNode(Node):
    def __init__(self):
        super().__init__('carla_navigator_node')
        
        self.subscription = self.create_subscription(
            String,
            '/assistant/navigation_goal',
            self.goal_callback,
            10
        )
        self.nav_thread = None
        self.get_logger().info("CARLA Navigator Node is online and waiting for destinations.")

    def goal_callback(self, msg):
        try:
            goal_data = json.loads(msg.data)
            target_lat = goal_data.get("latitude")
            target_lon = goal_data.get("longitude")
            dest_name = goal_data.get("destination_name", "Unknown Destination")
            
            self.get_logger().info(f"Received new navigation goal: {dest_name} (Lat: {target_lat}, Lon: {target_lon})")
            
            if self.nav_thread is not None and self.nav_thread.is_alive():
                self.get_logger().info("Overriding current route. Starting new path calculation...")
            
            self.nav_thread = threading.Thread(
                target=navigate_to_gnss, 
                args=(target_lat, target_lon),
                daemon=True
            )
            self.nav_thread.start()
            
        except Exception as e:
            self.get_logger().error(f"Failed to process navigation goal: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = CarlaNavigatorNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()