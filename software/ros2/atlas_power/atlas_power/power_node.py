"""ROS 2 node for the Atlas car v2 boards.

Publishes
  /battery      sensor_msgs/BatteryState  from atlas-battery.service (/run/atlas/battery.json)
  /estop_ok     std_msgs/Bool             E-stop loop closed (brain board expander P3)
  /charging     std_msgs/Bool             charger active (expander P4)
Serves
  /lidar_power  std_srvs/SetBool          lidar eFuse on/off (expander P2)

It never touches the INA228 itself: atlas-battery.service owns the charge counter. The atlas_hw
package comes from /opt/atlas (software/jetson/system/install.sh).
"""
import math
import sys

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool
from std_srvs.srv import SetBool

sys.path.append('/opt/atlas')
from atlas_hw import battery, board  # noqa: E402
from atlas_hw.expander import Expander  # noqa: E402
from atlas_hw.i2c import LinuxI2C  # noqa: E402


class PowerNode(Node):
    def __init__(self):
        super().__init__('atlas_power')
        rate = self.declare_parameter('rate_hz', 2.0).value
        self.battery_pub = self.create_publisher(BatteryState, 'battery', 10)
        self.estop_pub = self.create_publisher(Bool, 'estop_ok', 10)
        self.charging_pub = self.create_publisher(Bool, 'charging', 10)
        self.create_service(SetBool, 'lidar_power', self.on_lidar)
        self.exp = None
        try:
            self.exp = Expander(LinuxI2C(board.sys_i2c_bus()))
            self.exp.setup()
        except OSError as e:
            self.get_logger().error(f'brain board expander not reachable: {e}')
        self.charging = False
        self.create_timer(1.0 / rate, self.tick)

    def tick(self):
        if self.exp:
            try:
                self.estop_pub.publish(Bool(data=self.exp.estop_ok()))
                self.charging = self.exp.charging()
                self.charging_pub.publish(Bool(data=self.charging))
            except OSError as e:
                self.get_logger().warn(f'expander read failed: {e}', throttle_duration_sec=10.0)
        live = battery.read_live()
        msg = BatteryState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_LION
        msg.design_capacity = board.PACK_CAPACITY_AH
        msg.capacity = math.nan
        msg.charge = math.nan
        msg.temperature = math.nan
        msg.cell_voltage = [math.nan] * board.PACK_CELLS_SERIES
        msg.location = 'drive board pack'
        if live is None:
            msg.present = False
            msg.voltage = msg.current = msg.percentage = math.nan
            msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_UNKNOWN
            self.get_logger().warn('atlas-battery.service is not running', throttle_duration_sec=30.0)
        else:
            msg.present = True
            msg.voltage = float(live['voltage'])
            msg.current = -float(live['current'])       # ROS: negative while discharging
            msg.percentage = float(live['soc'])
            if self.charging:
                msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_CHARGING
            elif live['current'] > 0.05:
                msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
            else:
                msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_NOT_CHARGING
        self.battery_pub.publish(msg)

    def on_lidar(self, request, response):
        if not self.exp:
            response.success, response.message = False, 'expander not reachable'
            return response
        try:
            self.exp.lidar(request.data)
            response.success = True
            response.message = 'lidar power ' + ('on' if self.exp.lidar() else 'off')
        except (OSError, RuntimeError) as e:
            response.success, response.message = False, str(e)
        return response


def main():
    rclpy.init()
    node = PowerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
