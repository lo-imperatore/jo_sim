import os

from ament_index_python.packages import get_package_share_directory


from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from launch_ros.actions import Node
from pathlib import Path




def generate_launch_description():


    package_name='jo_sim'

    rviz_arg = DeclareLaunchArgument('rviz', default_value='false', description='Whether to launch RViz')

    rviz_config = os.path.join(
        get_package_share_directory(package_name),
        'rviz',
        'sim.rviz'
        )
    
    glim_config = os.path.join(get_package_share_directory(package_name), 'config', 'glim', 'glim_config_bunker_sim')

    
    glim_param_folder_arg = DeclareLaunchArgument(
        'glim_param',
        default_value=glim_config,
        description='GLIM param folder passed to its node'
    )

    launch_glim_arg = DeclareLaunchArgument(
        'glim',
        default_value='false',
        description='Whether to launch the GLIM stack'
    )
    

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': True}],
        condition=IfCondition(LaunchConfiguration('rviz'))
    )

    rsp = IncludeLaunchDescription(
                PythonLaunchDescriptionSource([os.path.join(
                    get_package_share_directory('jo_description'),'launch','description.launch.py'
                )]), launch_arguments={'use_sim_time': 'true', 'use_ros2_control': 'true'}.items()
    )
    
    # default_world = os.path.join(
    #     get_package_share_directory(package_name),
    #     'worlds',
    #     'external',
    #     'worlds',
    #     'yosemite.world'
    #     ) 

    default_world = os.path.join(
        get_package_share_directory(package_name),
        'worlds',
        'obstacles.sdf'
        )  
    
    world = LaunchConfiguration('world')

    world_arg = DeclareLaunchArgument(
        'world',
        default_value=default_world,
        description='World to load'
        )

    gazebo = IncludeLaunchDescription(
                    PythonLaunchDescriptionSource([os.path.join(
                        get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')]),
                        launch_arguments={'gz_args': ['-r -v3 ', world], 'on_exit_shutdown': 'true'}.items()
    )

    # Run the spawner node from the ros_gz_sim package. The entity name doesn't really matter if you only have a single robot.
    spawn_entity = Node(package='ros_gz_sim', executable='create',
                        arguments=['-topic', 'robot_description',
                                   '-name', 'jo',
                                   '-x', '0.0',
                                   '-y', '0.0',
                                   '-z', '4.7'],
                        output='screen')


    bridge_params = os.path.join(get_package_share_directory(package_name),'config','gz_bridge.yaml')
    ros_gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            '--ros-args',
            '-p',
            f'config_file:={bridge_params}',
        ]
    )

    ros_gz_image_bridge = Node(
        package="ros_gz_image",
        executable="image_bridge",
        arguments=["/front_camera/image", "/back_camera/image"],
    )


    glim = Node(
        package='glim_ros',
        executable='glim_rosnode',
        output='screen',
        emulate_tty=True,
        condition=IfCondition(LaunchConfiguration('glim')),
        additional_env={
            '__NV_PRIME_RENDER_OFFLOAD': '0',
            '__GLX_VENDOR_LIBRARY_NAME': '',
        },
        parameters=[
            {'config_path': LaunchConfiguration('glim_param')},
            {'use_sim_time' : True}
            ],
    )


    delayed_glim = TimerAction(
        period=4.0,
        actions=[
            glim
        ]
    )


    # Launch them all!
    return LaunchDescription([
        glim_param_folder_arg,
        launch_glim_arg,
        rsp,
        rviz_arg,
        world_arg,
        gazebo,
        spawn_entity,
        ros_gz_bridge,
        ros_gz_image_bridge,
        rviz,
        delayed_glim
    ])
