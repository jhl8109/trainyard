# 에피소드 1개를 설명하는 메타데이터. ty_recorder 가 에피소드마다 한 번
# /ty/episode_meta 에 싣고 rosbag2(MCAP) 안에 함께 기록한다.
# 데이터 파이프라인(platform/)과 평가 DB 가 이걸로 필터 · 버전 구분 · 조건 매칭을 한다.
#
# 실패 모드 코드와 성공 판정의 정의는 docs/task-pick-place.md §3 · §4 가 단일 출처다.
# 여기 상수는 그 문서의 코드를 그대로 옮긴 것이고, 문자열로 두는 이유는
# 성공 판정 함수(TY-106)가 ROS 2 없이 같은 코드를 반환하기 때문이다.

uint8 SOURCE_SIM=0
uint8 SOURCE_REAL=1

uint8 COLLECTION_TELEOP=0
uint8 COLLECTION_POLICY=1
uint8 COLLECTION_SCRIPTED=2

string FAILURE_NONE=
string FAILURE_GRASP_MISS=grasp_miss
string FAILURE_DROP=drop
string FAILURE_MISPLACE=misplace
string FAILURE_UNSETTLED=unsettled
string FAILURE_TIMEOUT=timeout
string FAILURE_UNSAFE=unsafe
string FAILURE_OUT_OF_BOUNDS=out_of_bounds

std_msgs/Header header

# UUID4. 파일명 · 평가 DB 키 · 라벨링 UI 가 공유하는 식별자.
string episode_id

# 태스크 이름. v0 은 "pick_place" 하나뿐이다.
string task_id

# config/task/*.yaml 의 해시. 조건표가 바뀐 뒤 수집된 데이터를 구분하기 위한 것으로,
# 이게 없으면 격자가 재측정된 뒤의 데이터와 이전 데이터가 섞인다
# (docs/task-pick-place.md §9).
string task_config_hash

# SOURCE_* — 시뮬에서 모았나 실물에서 모았나. v3 sim2real gap 분석의 축.
uint8 source

# COLLECTION_* — 사람이 몰았나 정책이 몰았나.
uint8 collection

# collection == COLLECTION_POLICY 일 때 어느 체크포인트인가. 아니면 "".
string policy_id

# 텔레오퍼레이터 식별자. collection == COLLECTION_TELEOP 일 때만 채운다.
# operator 는 C++ 예약어라 생성 코드가 깨지므로 operator_id 로 둔다.
string operator_id

# 씬 리셋 시드. 같은 조건을 다시 돌리기 위한 값이다 (docs/task-pick-place.md §6).
int32 seed

# 평가 조건표의 셀 id (격자 셀 · yaw · seed 조합). 자유 시연 수집이면 "".
string condition_id

builtin_interfaces/Time started_at
builtin_interfaces/Time ended_at

# docs/task-pick-place.md §3 의 placed AND settled AND intact 판정 결과.
bool success

# FAILURE_* 중 하나. success 가 true 면 FAILURE_NONE("").
string failure_mode

# ActionChunk 와 같은 관절 순서 계약. 기록된 토픽의 배열 순서를 이 메시지만 보고 해석할 수 있게 싣는다.
string[] joint_names

# 사람이 남기는 자유 메모 (예: "그리퍼 미끄러짐 관찰").
string notes
