"""ROS 2 node for Atlas car 2 (rev B: dev-kit carrier + ATLAS-PWR-1 power board).

Publishes
  /battery      sensor_msgs/BatteryState  from atlas-battery.service (/run/atlas/battery.json):
                pack voltage and current from the JBD BMS, cell voltages, temperature, estimate
  /estop_ok     std_msgs/Bool             E-stop loop closed (J12 pin 33, driven by the supervisor)
  /charging     std_msgs/Bool             charger connected (J12 pin 32, low = charging)
Serves
  /lidar_power  std_srvs/SetBool          lidar power, through the supervisor

It never opens the supervisor's USB port itself: atlas-battery.service owns it, and this node
asks through its socket. The E-stop and charger lines are read on the 40-pin header; if libgpiod
is missing or the lines are busy, the node falls back to the supervisor's status frame (up to
1 s old). The atlas_hw package comes from /opt/atlas (software/jetson/system/install.sh).
"""
import math
import sys

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool
from std_srvs.srv import SetBool

sys.path.append('/opt/atlas')
from atlas_hw import battery, board, gpio, supervisor  # noqa: E402


class PowerNode(Node):
    def __init__(self):
        super().__init__('atlas_power')
        rate = self.declare_parameter('rate_hz', 2.0).value
        self.battery_pub = self.create_publisher(BatteryState, 'battery', 10)
        self.estop_pub = self.create_publisher(Bool, 'estop_ok', 10)
        self.charging_pub = self.create_publisher(Bool, 'charging', 10)
        self.create_service(SetBool, 'lidar_power', self.on_lidar)
        self.lines = None
        try:
            self.lines = gpio.Lines(inputs=board.GPIO_INPUTS, consumer='atlas_power')
        except gpio.GpioUnavailable as e:
            self.get_logger().warn(f'J12 lines not available ({e}); using the supervisor status instead')
        self.charging = False
        self.create_timer(1.0 / rate, self.tick)

    def _inputs(self):
        """(estop_ok, charging) or (None, None)."""
        if self.lines is not None:
            try:
                return self.lines.get('ESTOP_OK') == 1, self.lines.get('CHG_STAT_N') == 0
            except OSError as e:
                self.get_logger().warn(f'J12 read failed: {e}', throttle_duration_sec=10.0)
        st = supervisor.read_live()
        if st is None:
            return None, None
        return bool(st.get('estop')), bool(st.get('chg'))

    def tick(self):
        estop_ok, charging = self._inputs()
        if estop_ok is not None:
            self.estop_pub.publish(Bool(data=estop_ok))
            self.charging = charging
            self.charging_pub.publish(Bool(data=charging))
        live = battery.read_live()
        msg = BatteryState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_LION
        msg.design_capacity = board.PACK_CAPACITY_AH
        msg.capacity = math.nan
        msg.charge = math.nan
        msg.temperature = math.nan
        msg.cell_voltage = [math.nan] * board.PACK_CELLS_SERIES
        msg.location = 'car 2 pack (JBD BMS)'
        if live is None:
            msg.present = False
            msg.voltage = msg.current = msg.percentage = math.nan
            msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_UNKNOWN
            self.get_logger().warn('atlas-battery.service is not running', throttle_duration_sec=30.0)
        else:
            msg.present = True
            msg.voltage = float(live['voltage'])
            msg.current = -float(live['current']) if live.get('current_known', True) else math.nan
            msg.percentage = float(live['soc'])
            if live.get('cells'):
                msg.cell_voltage = [float(c) for c in live['cells']]
            if live.get('temps'):
                msg.temperature = float(max(live['temps']))
            if live.get('full_ah') is not None:
                msg.capacity = float(live['full_ah'])
            if live.get('rem_ah') is not None:
                msg.charge = float(live['rem_ah'])
            if self.charging:
                msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_CHARGING
            elif live['current'] > 0.05:
                msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
            else:
                msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_NOT_CHARGING
        self.battery_pub.publish(msg)

    def on_lidar(self, request, response):
        try:
            reply = supervisor.DaemonClient().request({'cmd': 'lidar', 'on': bool(request.data)})
        except supervisor.SupervisorError as e:
            response.success, response.message = False, str(e)
            return response
        if reply.get('t') == 'err':
            response.success, response.message = False, reply.get('msg', 'error')
        else:
            response.success = True
            response.message = 'lidar power ' + ('on' if reply.get('on') else 'off')
        return response

    def destroy_node(self):
        if self.lines is not None:
            self.lines.release()
        super().destroy_node()


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
