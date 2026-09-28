from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package='atlas_power', executable='power_node', name='atlas_power', output='screen',
             parameters=[{'rate_hz': 2.0}]),
    ])
