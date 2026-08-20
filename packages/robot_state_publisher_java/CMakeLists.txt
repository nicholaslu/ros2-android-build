cmake_minimum_required(VERSION 3.5)
project(robot_state_publisher_java)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_export_jars REQUIRED)
find_package(ament_cmake_export_jni_libraries REQUIRED)
find_package(rcljava_common REQUIRED)
find_package(rclcpp REQUIRED)
find_package(robot_state_publisher REQUIRED)

include(CrossCompilingExtra)

if(CMAKE_CROSSCOMPILING)
  find_host_package(Java COMPONENTS Development REQUIRED)
else()
  find_package(Java COMPONENTS Development REQUIRED)
endif()
if(NOT ANDROID)
  find_package(JNI REQUIRED)
endif()
include(UseJava)
include(JavaExtra)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(NOT WIN32)
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

set(CMAKE_JAVA_COMPILE_FLAGS "-source" "1.6" "-target" "1.6")

# Must match JNIUtils.loadImplementation(), which derives the library name from the class name:
# org.ros2.robot_state_publisher.RobotStatePublisher
#   -> org_ros2_robot_state_publisher__robot_state_publisher__jni
# Note the double underscore -- the package segment already ends in "publisher".
set(_jni_target org_ros2_robot_state_publisher__robot_state_publisher)

add_library(${_jni_target} SHARED
  src/main/cpp/org_ros2_robot_state_publisher_RobotStatePublisher.cpp
)

if(WIN32)
  set_target_properties(${_jni_target} PROPERTIES
    PREFIX ""
    OUTPUT_NAME "${_jni_target}__jni"
  )
else()
  set_target_properties(${_jni_target} PROPERTIES
    PREFIX "lib"
    OUTPUT_NAME "${_jni_target}__jni"
  )
endif()

target_include_directories(${_jni_target}
  PUBLIC
  ${JNI_INCLUDE_DIRS}
)

# Linked through the exported namespaced targets rather than ament_target_dependencies(),
# which was removed in Lyrical. These carry their own include dirs and transitive deps.
target_link_libraries(${_jni_target}
  rclcpp::rclcpp
  robot_state_publisher::robot_state_publisher_node
)

ament_export_jni_libraries(${_jni_target})

install(TARGETS ${_jni_target}
  ARCHIVE DESTINATION lib/jni
  LIBRARY DESTINATION lib/jni
)

set(${PROJECT_NAME}_sources
  src/main/java/org/ros2/robot_state_publisher/RobotStatePublisher.java
  src/main/java/org/ros2/robot_state_publisher/RobotStatePublisherOptions.java
)

add_jar("${PROJECT_NAME}_jar"
  ${${PROJECT_NAME}_sources}
  OUTPUT_NAME
  ${PROJECT_NAME}
  INCLUDE_JARS
  ${rcljava_common_JARS}
)

install_jar("${PROJECT_NAME}_jar" "share/${PROJECT_NAME}/java")
ament_export_jars("share/${PROJECT_NAME}/java/${PROJECT_NAME}.jar")

ament_package()
