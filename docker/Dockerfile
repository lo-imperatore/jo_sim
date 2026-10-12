FROM osrf/ros:jazzy-desktop-full

ENV GZ_VERSION=harmonic
ARG DISTRO=jazzy

RUN apt update -y \
    && apt install -y python3-pip \
    nano \
    libxcb-cursor0 \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN pip install --break-system-packages ruamel.yaml PyQt6 ultralytics 

RUN apt update -y \
    && apt install -y ros-${DISTRO}-plotjuggler \
    ros-${DISTRO}-joint-state-publisher \
    ros-${DISTRO}-joint-state-publisher-gui \
    ros-${DISTRO}-gz-ros2-control \
    ros-${DISTRO}-teleop-twist-joy \
    ros-${DISTRO}-joy \
    ros-${DISTRO}-ros2-control \
    ros-${DISTRO}-ros2-controllers \
    ros-${DISTRO}-xacro \
    ros-${DISTRO}-rosbag2-storage-mcap \
    ros-${DISTRO}-rmw-cyclonedds-cpp \
    ros-${DISTRO}-realsense2-camera \
    ros-${DISTRO}-realsense2-description \
    ros-${DISTRO}-twist-mux \
    ros-${DISTRO}-nav2-common \
    ros-${DISTRO}-nav2-controller \
    ros-${DISTRO}-nav2-smoother \
    ros-${DISTRO}-nav2-planner \
    ros-${DISTRO}-nav2-behaviors \
    ros-${DISTRO}-nav2-bt-navigator \
    ros-${DISTRO}-nav2-waypoint-follower \
    ros-${DISTRO}-nav2-velocity-smoother \
    ros-${DISTRO}-nav2-lifecycle-manager \
    ros-${DISTRO}-nav2-dwb-controller \
    ros-${DISTRO}-nav2-navfn-planner \
    ros-${DISTRO}-nav2-rviz-plugins \
    ros-${DISTRO}-nav2-graceful-controller \
    ros-${DISTRO}-robot-localization \
    python3-rosdep \
    software-properties-common \
    ca-certificates \
    libmetis-dev \
    gnupg \
    wget \
    xterm \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN sudo curl https://packages.osrfoundation.org/gazebo.gpg --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
RUN sudo apt update
RUN sudo apt install -y gz-harmonic



# --- CUDA repo (Ubuntu 24.04) ---
RUN wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb \
 && dpkg -i cuda-keyring_1.1-1_all.deb \
 && wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-ubuntu2404.pin \
 && mv cuda-ubuntu2404.pin /etc/apt/preferences.d/cuda-repository-pin-600 

ENV CUDAToolkit_ROOT=/usr/local/cuda

RUN curl -s https://koide3.github.io/ppa/setup_ppa.sh | sudo bash
RUN sudo add-apt-repository -y ppa:koide3/iridescence
RUN apt update -y \
    && apt install -y libiridescence-dev \
    libgtsam-points-cuda13.1-dev \
    cuda-cudart-13-0 \
    cuda-nvcc-13-0 \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*


# Create a non-root user
ARG USERNAME=ros
ARG USER_UID=1000
ARG USER_GID=${USER_UID}
RUN if id -u ${USER_UID} ; then userdel `id -un ${USER_UID}` ; fi
RUN groupadd --gid ${USER_GID} ${USERNAME} 
RUN useradd --uid ${USER_UID} --gid ${USER_GID} -m ${USERNAME} \
    && apt update \
    && apt install -y sudo \
    && echo ${USERNAME} ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

RUN cd /home/ros/ \
    && git clone https://github.com/RobotecAI/RGLGazeboPlugin.git 
RUN cd /home/ros/RGLGazeboPlugin \
    && mkdir build \ 
    && cd build \ 
    && cmake .. \
    && make -j \
    && make install \
    && cd .. \
    && export IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/home/ros/RGLGazeboPlugin/install/RGLServerPlugin:$IGN_GAZEBO_SYSTEM_PLUGIN_PATH \ 
    && export IGN_GUI_PLUGIN_PATH=/home/ros/RGLGazeboPlugin/install/RGLVisualize:$IGN_GUI_PLUGIN_PATH



USER ros
# RUN sudo usermod -aG dialout ros
WORKDIR /home/$USERNAME/
RUN mkdir src

# GLIM
RUN cd src && git clone https://github.com/mlisi1/glim_ros2.git
RUN cd src && git clone https://github.com/koide3/glim.git

RUN cd src && git clone https://github.com/sutharsan-311/nav2_config.git

RUN cd RGLGazeboPlugin && sudo touch COLCON_IGNORE

SHELL ["/bin/bash", "-c"]
RUN source /opt/ros/jazzy/setup.bash \
 && colcon build

COPY docker/entrypoint.sh /entrypoint.sh
RUN sudo chmod +x /entrypoint.sh
RUN echo "export GZ_SIM_SYSTEM_PLUGIN_PATH=/opt/ros/humble/lib/" >> ~/.bashrc
RUN cd RGLGazeboPlugin \
    && echo "export GZ_SIM_SYSTEM_PLUGIN_PATH=/opt/ros/humble/lib/" >> ~/.bashrc \
    && echo "export RGL_PATTERNS_DIR=`pwd`/lidar_patterns" >> ~/.bashrc \
    && echo "export GZ_SIM_SYSTEM_PLUGIN_PATH=`pwd`/install/RGLServerPlugin:$GZ_SIM_SYSTEM_PLUGIN_PATH" >> ~/.bashrc \
    && echo "export GZ_GUI_PLUGIN_PATH=`pwd`/install/RGLVisualize:$GZ_GUI_PLUGIN_PATH" >> ~/.bashrc \
    && echo "export GZ_SIM_RESOURCE_PATH=$GZ_SIM_RESOURCE_PATH:/home/ros/src/jo_sim/worlds/external/worlds/" >> ~/.bashrc \
    && echo "export GZ_SIM_RESOURCE_PATH=$GZ_SIM_RESOURCE_PATH:/home/ros/src/jo_sim/worlds/external/models/" >> ~/.bashrc 


COPY docker/utilities.sh /etc/utilities.sh
RUN echo 'source /etc/utilities.sh' >> ~/.bashrc

ENTRYPOINT ["/entrypoint.sh"]