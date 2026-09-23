from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('model_path', description='Absolute path to face_landmarker.task'),
        DeclareLaunchArgument('image_topic', default_value='/camera/image_raw'),
        Node(package='fred_hri', executable='perception_node', output='screen',
             parameters=[{'model_path': LaunchConfiguration('model_path')}],
             remappings=[('/camera/image_raw', LaunchConfiguration('image_topic'))]),
        Node(package='fred_hri', executable='hri_coordinator_node', output='screen'),
        Node(package='fred_hri', executable='display_gateway_node', output='screen'),
    ])
