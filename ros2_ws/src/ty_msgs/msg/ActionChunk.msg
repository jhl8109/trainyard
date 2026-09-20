# 정책 추론 노드가 한 번의 추론으로 내놓는 액션 청크.
# 제어 루프가 이걸 받아 /ty/joint_command 로 한 스텝씩 펼친다.
#
# 단위 · 순서는 joint_names 가 고정한다 (docs/task-pick-place.md §1):
#   shoulder_pan · shoulder_lift · elbow_flex · wrist_flex · wrist_roll  → 라디안, 베이스 프레임 기준
#   gripper                                                             → 0(닫힘) ~ 1(열림) 정규화
#
# positions 는 horizon × dof 행렬을 row-major 로 편 것이다.
#   k 번째 스텝(0-based) j 번째 관절 = positions[k * dof + j]
#   k 번째 스텝의 목표 시각          = valid_from + k * dt
# IDL 에 고정 크기 2차원 배열이 없어서 1차원 + (horizon, dof) 로 푼다.
# 시뮬과 실물이 같은 메시지를 쓰므로 여기에는 시뮬 전용 필드를 넣지 않는다.

# 이 청크를 만들어낸 관측의 시각. 스테일니스(관측 → 적용 지연)를 재는 기준이고,
# valid_from 과 달리 과거를 가리킨다.
std_msgs/Header header

# 첫 스텝을 적용할 시각. 추론 지연을 감추기 위해 보통 header.stamp 보다 앞선다.
# 수신 시점이 이미 valid_from 을 지났으면 제어 루프가 지난 스텝을 건너뛴다.
builtin_interfaces/Time valid_from

# 스텝 간격. v0 제어 주기는 20ms(50Hz).
builtin_interfaces/Duration dt

# 청크 길이. v0 기본값 20 (= 0.4초, docs/task-pick-place.md §5).
uint16 horizon

# 관절 수. SO-101 팔로워는 팔 5 + 그리퍼 1 = 6.
uint8 dof

# 길이 = dof. 값의 순서를 정의하는 계약이므로 매 메시지에 싣는다.
string[] joint_names

# 길이 = horizon * dof. 관절 위치 목표.
float32[] positions

# 이 청크를 낸 체크포인트. 모델 레지스트리 키이고, 텔레오퍼레이션이면 "".
# 재현을 위해 기록 시점에 어느 정책이 움직였는지 남긴다.
string policy_id
