source /opt/ros/jazzy/setup.bash
source /home/ros/install/setup.bash
source /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash
alias no_gpu='__NV_PRIME_RENDER_OFFLOAD=0 __GLX_VENDOR_LIBRARY_NAME='

alias localization='ros2 launch jo_navigation localization.launch.py use_sim_time:=true'
alias localization_gps='ros2 launch jo_navigation localization_gps.launch.py use_sim_time:=true'

alias navigation='ros2 launch jo_navigation navigation_local.launch.py rviz:=true use_sim_time:=true'
alias navigation_gps='ros2 launch jo_navigation navigation_gps.launch.py rviz:=true use_sim_time:=true'

alias sim='ros2 launch jo_sim launch_sim.launch.py glim:=true'

# Real-robot bag → GLIM map reconstruction (campo_ippodromo by default)
# Map dump is written under /home/ros/maps when GLIM exits (Ctrl-C or bag end).
alias bag_glim='ros2 launch jo_sim launch_bag_glim.launch.py'
alias bag_glim_yolo='ros2 launch jo_sim launch_bag_glim.launch.py yolo:=true rviz:=true'

# Inspect / export a saved dump with the offline viewer
alias glim_view='ros2 run glim_ros offline_viewer'