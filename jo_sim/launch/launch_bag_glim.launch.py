"""Reconstruct a map from a real-robot rosbag with GLIM.

Two backends
------------
* ``rosbag`` (default) – ``glim_rosbag`` reads the bag offline, auto-throttles
  so mapping does not drop frames, and writes a dump on exit. Best for map quality.
* ``node`` – live ``glim_rosnode`` + ``ros2 bag play``. Needed when you also want
  YOLO / RViz consuming the same camera stream.

Examples
--------
.. code-block:: bash

    # Map only (recommended)
    ros2 launch jo_sim launch_bag_glim.launch.py

    # Map + YOLO feature detection on the RealSense color stream
    ros2 launch jo_sim launch_bag_glim.launch.py yolo:=true rviz:=true

    # Slow playback if the GPU falls behind in node mode
    ros2 launch jo_sim launch_bag_glim.launch.py backend:=node rate:=0.5
"""

import os
from datetime import datetime

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    LogInfo,
    OpaqueFunction,
    TimerAction,
)
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


# Sensor topics for live bag play (node backend). Exclude /tf and old /glim_ros/*
# so the live mapper owns the transform tree.
GLIM_BAG_TOPICS = [
    '/velodyne_points',
    '/imu/data',
]

CAMERA_BAG_TOPICS = [
    '/front_camera/camera/color/image_raw/compressed',
    '/front_camera/camera/color/camera_info',
]


def _truthy(value: str) -> bool:
    return value.lower() in ('true', '1', 'yes', 'on')


def _launch_setup(context, *args, **kwargs):
    package_name = 'jo_sim'
    share = get_package_share_directory(package_name)

    bag_path = LaunchConfiguration('bag').perform(context)
    glim_config = LaunchConfiguration('glim_param').perform(context)
    dump_path = LaunchConfiguration('dump_path').perform(context)
    rate = LaunchConfiguration('rate').perform(context)
    start_offset = LaunchConfiguration('start_offset').perform(context)
    backend = LaunchConfiguration('backend').perform(context).lower()
    yolo_enabled = _truthy(LaunchConfiguration('yolo').perform(context))
    rviz_enabled = _truthy(LaunchConfiguration('rviz').perform(context))
    loop = _truthy(LaunchConfiguration('loop').perform(context))
    auto_quit = _truthy(LaunchConfiguration('auto_quit').perform(context))

    if yolo_enabled and backend == 'rosbag':
        # glim_rosbag reads the bag internally and does not republish camera topics.
        backend = 'node'

    os.makedirs(dump_path, exist_ok=True)

    actions = [
        LogInfo(msg=[
            f'[bag_glim] backend={backend} bag={bag_path} config={glim_config} dump={dump_path}'
        ]),
    ]

    if backend == 'rosbag':
        # Offline mapper: reads bag, throttles itself, dumps map on exit.
        glim_cmd = [
            'ros2', 'run', 'glim_ros', 'glim_rosbag', bag_path,
            '--ros-args',
            '-p', f'config_path:={glim_config}',
            '-p', f'dump_path:={dump_path}',
            '-p', f'auto_quit:={str(auto_quit).lower()}',
        ]
        actions.append(
            ExecuteProcess(
                cmd=glim_cmd,
                output='screen',
                additional_env={
                    '__NV_PRIME_RENDER_OFFLOAD': '0',
                    '__GLX_VENDOR_LIBRARY_NAME': '',
                    'RMW_IMPLEMENTATION': os.environ.get(
                        'RMW_IMPLEMENTATION', 'rmw_cyclonedds_cpp'
                    ),
                },
            )
        )
    else:
        # Live node + selective bag play.
        glim = Node(
            package='glim_ros',
            executable='glim_rosnode',
            name='glim_ros',
            output='screen',
            emulate_tty=True,
            additional_env={
                '__NV_PRIME_RENDER_OFFLOAD': '0',
                '__GLX_VENDOR_LIBRARY_NAME': '',
            },
            parameters=[
                {'config_path': glim_config},
                {'dump_path': dump_path},
                {'use_sim_time': True},
            ],
        )

        topics = list(GLIM_BAG_TOPICS)
        if yolo_enabled or rviz_enabled:
            topics.extend(CAMERA_BAG_TOPICS)

        play_cmd = [
            'ros2', 'bag', 'play', bag_path,
            '--clock',
            '--rate', rate,
            '--topics', *topics,
        ]
        if float(start_offset) > 0.0:
            play_cmd.extend(['--start-offset', start_offset])
        if loop:
            play_cmd.append('--loop')

        bag_play = ExecuteProcess(
            cmd=play_cmd,
            output='screen',
            additional_env={
                'RMW_IMPLEMENTATION': os.environ.get(
                    'RMW_IMPLEMENTATION', 'rmw_cyclonedds_cpp'
                ),
            },
        )

        # Let GLIM subscribe before the bag starts streaming.
        actions.extend([glim, TimerAction(period=2.0, actions=[bag_play])])

    if yolo_enabled:
        republish = Node(
            package='image_transport',
            executable='republish',
            name='front_camera_republish',
            output='screen',
            arguments=['compressed', 'raw'],
            remappings=[
                ('in/compressed', '/front_camera/camera/color/image_raw/compressed'),
                ('out', '/front_camera/camera/color/image_raw'),
            ],
            parameters=[{'use_sim_time': True}],
        )
        yolo = Node(
            package='jo_sim',
            executable='yolo_detector.py',
            name='yolo_detector',
            output='screen',
            parameters=[{
                'use_sim_time': True,
                'image_topic': '/front_camera/camera/color/image_raw',
                'annotated_topic': '/yolo/image_annotated',
                'detections_topic': '/yolo/detections',
                'model': LaunchConfiguration('yolo_model').perform(context),
                'confidence': float(LaunchConfiguration('yolo_confidence').perform(context)),
                'device': LaunchConfiguration('yolo_device').perform(context),
                'imgsz': int(LaunchConfiguration('yolo_imgsz').perform(context)),
            }],
        )
        actions.extend([
            republish,
            TimerAction(period=3.0, actions=[yolo]),
        ])

    if rviz_enabled:
        rviz_config = os.path.join(share, 'rviz', 'bag_glim.rviz')
        if not os.path.exists(rviz_config):
            rviz_config = os.path.join(share, 'rviz', 'sim.rviz')
        actions.append(
            Node(
                package='rviz2',
                executable='rviz2',
                name='rviz2',
                output='screen',
                arguments=['-d', rviz_config],
                parameters=[{'use_sim_time': True}],
            )
        )

    return actions


def generate_launch_description():
    package_name = 'jo_sim'
    default_glim = os.path.join(
        get_package_share_directory(package_name),
        'config', 'glim', 'glim_config_bunker',
    )
    # Host paths inside the container (see compose.yaml volume mounts).
    default_bag = '/home/ros/bags/20260722_093857_campo_ippodromo'
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    default_dump = f'/home/ros/maps/campo_ippodromo_{stamp}'

    return LaunchDescription([
        DeclareLaunchArgument(
            'bag',
            default_value=default_bag,
            description='Path to the rosbag2 directory to replay',
        ),
        DeclareLaunchArgument(
            'glim_param',
            default_value=default_glim,
            description='GLIM config folder (glim_config_bunker for real robot bags)',
        ),
        DeclareLaunchArgument(
            'dump_path',
            default_value=default_dump,
            description='Where GLIM writes the map dump on exit',
        ),
        DeclareLaunchArgument(
            'backend',
            default_value='rosbag',
            description="Mapping backend: 'rosbag' (glim_rosbag) or 'node' (glim_rosnode + bag play)",
        ),
        DeclareLaunchArgument(
            'auto_quit',
            default_value='true',
            description='For rosbag backend: exit and save dump when the bag ends',
        ),
        DeclareLaunchArgument(
            'rate',
            default_value='1.0',
            description='Bag playback rate (node backend only)',
        ),
        DeclareLaunchArgument(
            'start_offset',
            default_value='0.0',
            description='Skip this many seconds at bag start (node backend only)',
        ),
        DeclareLaunchArgument(
            'loop',
            default_value='false',
            description='Loop bag playback (node backend only)',
        ),
        DeclareLaunchArgument(
            'yolo',
            default_value='false',
            description='Run YOLO on the front RealSense color stream (forces node backend)',
        ),
        DeclareLaunchArgument(
            'yolo_model',
            default_value='yolov8n.pt',
            description='Ultralytics model name or path',
        ),
        DeclareLaunchArgument(
            'yolo_confidence',
            default_value='0.35',
            description='Minimum detection confidence',
        ),
        DeclareLaunchArgument(
            'yolo_device',
            default_value='cuda:0',
            description="Inference device: 'cuda:0' or 'cpu'",
        ),
        DeclareLaunchArgument(
            'yolo_imgsz',
            default_value='640',
            description='YOLO inference image size',
        ),
        DeclareLaunchArgument(
            'rviz',
            default_value='false',
            description='Launch RViz (use with backend:=node or yolo:=true)',
        ),
        OpaqueFunction(function=_launch_setup),
    ])
