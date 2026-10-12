cmake_minimum_required(VERSION 3.5.1)
project(jo_sim)

find_package(ament_cmake)

install(
  DIRECTORY config launch worlds rviz
  DESTINATION share/${PROJECT_NAME}
)

install(
  PROGRAMS
    scripts/yolo_detector.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
