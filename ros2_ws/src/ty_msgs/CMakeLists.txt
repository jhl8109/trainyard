cmake_minimum_required(VERSION 3.8)
project(ty_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(std_msgs REQUIRED)

# 메시지 정의는 TY-9에서 추가한다 (ActionChunk · EpisodeMeta).
# msg/ 에 파일이 생기면 아래를 살린다:
#
# rosidl_generate_interfaces(${PROJECT_NAME}
#   "msg/ActionChunk.msg"
#   "msg/EpisodeMeta.msg"
#   DEPENDENCIES builtin_interfaces std_msgs
# )
# ament_export_dependencies(rosidl_default_runtime)

ament_package()
