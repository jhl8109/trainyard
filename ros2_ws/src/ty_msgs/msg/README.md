# ty_msgs/msg

`.msg` 정의가 들어가는 자리. TY-9에서 `ActionChunk`(horizon · dof · valid_from)와
`EpisodeMeta`를 추가하고, 같은 PR에서 `CMakeLists.txt`의
`rosidl_generate_interfaces` 블록을 활성화한다.

필드·단위·관절 순서의 근거는 `docs/interfaces.md`(TY-10에서 생성)에 적는다.
