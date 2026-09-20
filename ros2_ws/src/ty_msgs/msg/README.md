# ty_msgs/msg

시뮬 · 실물 · 기록 · 추론이 공유하는 메시지 계약. 여기를 바꾸면 네 곳이 동시에 흔들리므로,
필드를 더하거나 의미를 바꾸는 변경은 `docs/interfaces.md`(TY-10)를 같이 고친다.

| 메시지 | 누가 낸다 | 누가 받는다 |
|---|---|---|
| `ActionChunk` | `ty_policy` 추론 노드 | 제어 루프 — 한 스텝씩 `/ty/joint_command` 로 편다 |
| `EpisodeMeta` | `ty_recorder` | rosbag2(MCAP) 기록 · 데이터 파이프라인 · 평가 DB |

공통 계약:

- **관절 순서** `shoulder_pan · shoulder_lift · elbow_flex · wrist_flex · wrist_roll · gripper`
  (`docs/task-pick-place.md` §1). 두 메시지 모두 `joint_names` 를 실어, 기록만 보고도 배열을 해석할 수 있게 한다.
- **단위** 팔 관절은 라디안, 그리퍼는 0(닫힘)~1(열림) 정규화. 미터 · 라디안 · 초.
- **타이밍** `ActionChunk` 는 `valid_from` 과 `dt` 로 자기 시간을 스스로 설명한다. 제어 주기(v0 20ms)나
  horizon(v0 20)을 메시지에 상수로 박지 않은 것은, 그 숫자가 config 이고 v2 에서 실측으로 바뀌기 때문이다.
- **실패 모드 코드**는 `EpisodeMeta` 의 `FAILURE_*` 상수. 값은 `docs/task-pick-place.md` §4 의 7종 문자열과
  같고, ROS 2 없이 도는 성공 판정 함수(TY-106)가 같은 코드를 돌려준다.
