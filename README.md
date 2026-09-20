# TrainYard

로봇팔이 사람의 시연을 보고 작업을 배우고(모방학습), 그 정책이 ROS 2 위에서 실시간으로 돌아가기까지의 전 과정 — 텔레오퍼레이션 · 데이터 파이프라인 · 학습 · 평가 · 온보드 추론 — 을 하나의 시스템으로 만드는 프로젝트.

시뮬레이션(MuJoCo)에서 파이프라인을 먼저 완성하고, 같은 인터페이스 그대로 실물 로봇팔(SO-101)로 옮긴다. 실물까지 도달한 뒤 그 위에 RL 파인튜닝을 얹는다.

## 범위

모델 구조를 새로 설계하는 것은 이 프로젝트의 범위가 아니다. 정책은 검증된 구현(BC · ACT · SmolVLA)을 쓰고, 산출물은 **그 정책을 실제로 돌아가게 만드는 시스템** — 텔레오퍼레이션 데이터 수집, 재현 가능한 평가 인프라, 실시간 온보드 추론, ROS 2 통합 — 이다.

"정책이 동작한다"의 기준은 데모 영상이 아니라 고정된 조건표 위의 수치다. 성공률 · 완료 시간 · 추론 레이턴시 p50/p99 · 제어 루프 deadline miss 비율을 모든 릴리즈에서 같은 방식으로 남긴다.

## 설계 원칙

1. **시뮬레이션과 실물은 인터페이스가 같다.** 로봇 하드웨어 계층을 추상화해 MuJoCo 시뮬레이션과 실물 SO-101을 드라이버 교체만으로 바꿔 끼운다. 텔레오퍼레이션 · 기록 · 추론 · 평가 코드는 어느 쪽인지 모른다.
2. **데이터는 서비스처럼 다룬다.** 수집된 에피소드는 자동 검증을 통과해야 데이터셋이 되고, 데이터셋은 버전이 붙고, 모든 모델은 어떤 데이터셋 버전으로 학습됐는지 추적된다.
3. **평가는 재현 가능해야 한다.** 고정된 평가 조건(물체 위치 · 조명 · seed)으로만 모델을 비교한다. "잘 되는 것 같다"는 결과로 치지 않는다.
4. **정책 학습 기본기는 직접 짠다.** Behavior Cloning을 PyTorch로 밑바닥부터 구현한 뒤 ACT 같은 검증된 구현을 쓴다. RL도 같은 순서로 — residual policy와 학습 루프를 직접 짠다.
5. **모방학습이 기본, RL은 그 위에 얹는다.** 처음부터 RL로 탐색하지 않는다. IL로 동작하는 정책을 먼저 만들고, 실패하는 구간만 RL로 다듬는다. 탐색 문제를 없애고 시작하는 쪽이 샘플 효율·개발 시간 모두에서 유리하다.
6. **모든 릴리즈는 그 자체로 완결된다.** 각 단계가 독립적으로 동작하는 데모와 수치를 남긴다. CI는 v0부터 붙인다.

## 아키텍처

```
┌─ 로봇 런타임 (ROS 2 Jazzy) ──────────────────────────────────────────┐
│                                                                       │
│  Teleop 입력 ──> Controller (C++, 50Hz) ──> Hardware Interface ──> rosbag2 recorder
│  게임패드/리더암        ▲                     MuJoCo ↔ SO-101        │ (MCAP)
│                         │ action chunk             │ 관측             │
│                  Policy 추론 노드 <───────────────┘                  │
│                  Python · ONNX/TensorRT                               │
└───────────────────────▲──────────────────────────────────────────────┼┘
                        │ 배포                                          ▼
┌─ 플랫폼 (FastAPI + PostgreSQL) ─────────────────────────────────────────┐
│  평가 DB · UI  <──  Model Registry  <──  Job Queue  <──  Data Pipeline   │
│  (실험 비교)         (체크포인트)        (PG SKIP LOCKED)  (검증→변환→버전)│
│                            ▲                  │                          │
│                            │          ┌───────┴────────┐                 │
│                            ├──────────┤ IL 학습 (BC/ACT)│                 │
│                            └──────────┤ RL 파인튜닝     │                 │
│                                       │ MuJoCo 병렬 env │                 │
│                                       └────────────────┘                 │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Hardware Interface**: 시뮬레이션/실물 교체 지점. 관절 상태 · 카메라 · 관절 목표 토픽 규약을 고정한다.
- **Controller ↔ Policy**: 50Hz 실시간 제어 루프(C++)와 비동기 추론(Python)을 action chunk 버퍼로 분리한다. 추론이 늦어도 제어 루프는 멈추지 않는다.
- **Data Pipeline**: rosbag2(MCAP) → 검증(프레임 드롭 · 타임스탬프 동기 · 관절 한계 · 에피소드 길이) → LeRobot 데이터셋 포맷 변환 → 버전 등록.
- **Job Queue**: PostgreSQL 테이블 큐(`SELECT … FOR UPDATE SKIP LOCKED`), 상태 머신 `queued → running → succeeded | failed | cancelled`, 체크포인트 기반 재개, 재현성 메타데이터(git SHA · config 해시 · 데이터셋 버전). IL 학습 · RL 파인튜닝 · 평가 잡이 같은 큐를 쓴다.
- **RL 파인튜닝**: 동결된 IL 정책 위에 residual policy를 올려 시뮬에서 학습한다. 보상은 v1 평가 성공 판정 로직을 그대로 재사용한다.

## 레포 구조

```
trainyard/
├── ros2_ws/src/        로봇 런타임 — colcon이 빌드하는 ROS 2 패키지
│   ├── ty_msgs/          인터페이스 메시지 (ActionChunk · EpisodeMeta)
│   ├── ty_sim/           MuJoCo Hardware Interface 노드
│   ├── ty_teleop/        게임패드 → IK → joint_command
│   ├── ty_recorder/      에피소드 세션 · rosbag2(MCAP) 기록
│   ├── ty_policy/        정책 추론 노드
│   └── ty_bringup/       launch 파일
├── platform/           ROS 바깥 — 데이터 · 학습 · 평가 · 잡 큐 (`trainyard` 패키지)
│   ├── src/trainyard/    sim · data · policies · training · evaluation · api
│   └── tests/
├── config/             양쪽이 공유하는 설정 (태스크 정의)
├── scripts/            환경 검증 등 개발 스크립트
└── docs/               설계 · 계약 · 셋업 문서
```

가르는 기준은 하나다. **ROS 2를 source 해야 돌아가는 코드만 `ros2_ws/`에 둔다.** 학습·평가·API는
로봇이 없어도 돌아야 하고 CI에서도 ROS 없이 테스트되므로 `platform/`에 남는다. 둘이 만나는 지점은
`ty_policy`(체크포인트를 읽어 추론)와 `config/`(같은 태스크 정의 파일) 두 곳뿐이다.

| 아키텍처 구성요소 | 사는 곳 |
|---|---|
| Hardware Interface · Controller | `ros2_ws/src/ty_sim` → v3에서 `ty_hw_so101`로 교체 |
| Teleop 입력 | `ros2_ws/src/ty_teleop` |
| rosbag2 recorder | `ros2_ws/src/ty_recorder` |
| Policy 추론 노드 | `ros2_ws/src/ty_policy` |
| MuJoCo 씬 (MJCF · 도달성 측정) | `platform/src/trainyard/sim` |
| Data Pipeline · Model Registry · Job Queue · 평가 DB | `platform/src/trainyard/` |
| IL 학습 · RL 파인튜닝 | `platform/src/trainyard/{training,policies}` |

50Hz C++ 제어 루프(`ty_control`)와 실물 서보 드라이버(`ty_hw_so101`)는 각각 v2 · v3에서 추가된다.
지금 빈 패키지로 만들어두지 않는 것은, 인터페이스가 고정되기 전에 껍데기를 먼저 박으면
그 껍데기가 설계를 끌고 가기 때문이다.

### 빌드와 테스트

```bash
# 플랫폼 (ROS 불필요)
pytest

# ROS 2 워크스페이스
scripts/build.sh                    # 전체 빌드
scripts/build.sh --test             # 빌드 + colcon test + 실패 요약
scripts/build.sh ty_msgs ty_sim     # 그 패키지와 의존 패키지까지
scripts/build.sh --clean            # build/ install/ log/ 지우고 처음부터

source scripts/env.sh               # 빌드 결과를 셸에 붙인다 (ros2 run · launch 하기 전)
```

`scripts/env.sh`는 ROS 2 underlay → `ros2_ws/install` 오버레이 → venv 순으로 한 셸에 얹는다.
`.venv/bin`을 `PATH`에 넣지 않고 venv의 `site-packages`만 `PYTHONPATH`에 붙이는데,
`requirements.txt`가 고정한 pip cmake 4.x가 apt cmake 3.28을 가리면 ROS 2 패키지의
`cmake_minimum_required`를 거부해 빌드가 깨지기 때문이다. 파이썬 인터프리터가 직접 필요하면
`$TY_PYTHON`(= `.venv/bin/python`)을 쓴다.

빌드 옵션은 `ros2_ws/colcon-defaults.yaml` 한 곳에 있다. `scripts/env.sh`가
`COLCON_DEFAULTS_FILE`로 가리키므로 `colcon`을 직접 쳐도 래퍼와 같은 옵션이 걸린다.

린터 설정은 TY-4, CI는 TY-5에서 붙인다.

## 로드맵

| 릴리즈 | 범위 | 기간 | 상태 |
|---|---|---|---|
| v0 | NVIDIA 드라이버 · ROS 2 Jazzy 셋업 · MuJoCo 로봇팔 + Hardware Interface · 게임패드 텔레오퍼레이션(IK) · rosbag2 기록 · CI. 사이드: PyTorch BC 밑바닥 구현 | 3–4주 | 다음 시작 |
| v1 | 데이터 파이프라인(검증 → 변환 → 버전) · ACT 학습 · 시뮬 평가 프로토콜 · Job 큐 · 평가 DB · 비교 UI | +3–4주 | 계획 |
| v2 | 실시간 추론 아키텍처 — C++ 제어 루프 + 비동기 추론 노드 · action chunking · 레이턴시 예산 측정 · ONNX/TensorRT · 양자화 전후 비교. *SO-101 주문* | +3주 | 계획 |
| v3 | 실물 전환 + sim2real — ROS 2 서보 드라이버 · 캘리브레이션 · 리더-팔로워 텔레오퍼레이션 · 실데이터 수집 · 실로봇 평가 + 라벨링 UI · 시스템 식별 · 도메인 랜덤화 · gap 측정과 ablation | +4–5주 | 계획 |
| v4 | **RL 파인튜닝** — 상태 기반 residual RL · 보상 설계 · 병렬 환경 처리량 · IL vs IL+RL 비교 · **RL 정책의 sim2real 재검증** | +3–4주 | 계획 |
| v5 (선택) | VLA(SmolVLA급) 파인튜닝 · 멀티스텝 태스크 · Docker Compose 폴리싱 | +2–3주 | 여력 시 |

전체 v0–v4 **16–20주** (+v5 선택 2–3주).

### v0–v1에 미리 박아두는 RL 대비 제약

RL을 v4로 미루되, 그때 가서 파이프라인을 뜯지 않도록 앞단에서 세 가지만 지킨다. 비용은 거의 없다.

- **MuJoCo 모델을 MJX 호환으로 유지한다** (v0). v4에서 처리량이 모자라면 GPU 병렬로 옮겨야 하는데, 모델 XML이 MJX 미지원 기능을 쓰고 있으면 그때 다시 만들어야 한다.
- **평가 성공 판정을 독립 함수로 분리한다** (v1). RL 보상의 핵심 항이 곧 평가 성공 판정이다. 같은 코드를 쓰면 "평가 기준과 학습 목표가 다른" 사고가 원천 차단된다.
- **정책 인터페이스를 추상화한다** (v1). `observation → action chunk` 시그니처를 고정해서 BC · ACT · ACT+residual이 평가 코드 입장에서 구분되지 않게 한다.

### v4 상세 — RL을 왜 sim2real *뒤*에 두는가

RL 파인튜닝 자체는 시뮬 작업이지만 v3 뒤에 배치한다. 이유는 v3의 실물 인프라가 있어야 v4가 답할 수 있는 질문이 달라지기 때문이다.

- v3 없이 v4를 하면 결론이 **"시뮬 성공률이 82% → 89%로 올랐다"** 에서 끝난다.
- v3 뒤에 하면 **"시뮬에서 올린 7%p가 실물에서도 남는가"** 를 물을 수 있다. RL 정책은 시뮬 물리의 빈틈을 파고들어 실물에서 무너지는 일이 흔해서, 이 질문 자체가 결과다.

구성:

- **알고리즘**: 동결된 ACT 정책 + 작은 residual policy(MLP)를 SAC 또는 PPO로 학습. ACT 내부를 건드리지 않아 IL 자산을 그대로 재사용한다.
- **관측**: 상태 기반(관절각 · 관절속도 · 물체 pose · 목표 pose). 비전을 빼서 학습을 빠르게 하고, 정책 본체(ACT)가 이미 비전을 담당한다.
- **보상**: v1 평가 성공 판정 + shaping(목표 거리 · 저크 페널티 · 관절 한계 페널티).
- **처리량**: CPU 병렬 16–32 env로 시작. 1e7 스텝을 넘어가면 MJX(GPU 병렬)로 전환.
- **산출물**: 동일 평가 세트에서 BC / ACT / ACT+RL 3단 비교표, 그리고 v3 실물 조건표에서의 재평가.

## 기술 스택

| 영역 | 선택 |
|---|---|
| 로봇 미들웨어 | ROS 2 Jazzy (Linux Mint 22 = Ubuntu 24.04 기반) |
| 시뮬레이션 | MuJoCo (SO-ARM 계열 팔 모델) · v4에서 필요 시 MJX |
| 실물 로봇 | SO-101 리더 + 팔로워 (v3) |
| 데이터 | rosbag2 (MCAP) → LeRobot 데이터셋 포맷 |
| 모방학습 | PyTorch — 자체 BC, ACT (LeRobot 구현) |
| 강화학습 (v4) | PyTorch — residual policy + SAC/PPO (자체 구현, 필요 시 SB3 참조) |
| VLA (v5, 선택) | SmolVLA급 파인튜닝 |
| 추론 | 제어 루프 C++(rclcpp), 추론 Python(rclpy) · ONNX Runtime / TensorRT |
| 플랫폼 | FastAPI · PostgreSQL(큐 + 메타데이터) · 비교 UI |
| CI | GitHub Actions — 린트 · 단위 테스트 · 시뮬 스모크 테스트 |

## 하드웨어

- CPU: AMD Ryzen 5 5600 (6C/12T)
- GPU: RTX 4060 Ti **8GB** — ACT 학습 · 추론, 상태 기반 RL, SmolVLA급 파인튜닝까지
- RAM: 32GB
- OS: Linux Mint 22.3
- 드라이버: `nvidia-driver-595-open` 595.91.07 — CUDA 13.2 · sm_89 동작 확인 (검증 절차는 [`scripts/verify_env.sh`](scripts/verify_env.sh))

실물(v3): SO-101 리더 + 팔로워, USB 웹캠 2대(탑뷰 · 손목), 예비 STS3215 서보. v2 시작 시 주문해 배송 · 조립 리드타임을 확보한다.

DIY 키트 대신 조립완성품을 쓴다. 3D 프린팅과 프레임 조립은 이 프로젝트가 증명하려는 것이 아니고, 그 시간은 소프트웨어 스택에 쓴다.

## 평가 프로토콜 (v1에서 확정)

- 태스크: pick-and-place (정해진 물체를 목표 영역에 놓기)
- 평가 세트: 물체 초기 위치 격자 × 물체 종류 × seed — 학습 데이터에 없는 위치 포함
- 지표: 성공률, 완료 시간, 추론 레이턴시(p50/p99), 제어 루프 deadline miss 비율
- 비교 축: **BC / ACT / ACT+RL** × **시뮬 / 실물**. 같은 조건표로만 비교한다.
- 실물(v3): 같은 조건표로 수행하고 결과는 UI에서 라벨링, 시뮬 결과와 나란히 비교

## 개발 워크플로

트렁크 기반. `develop` 브랜치는 쓰지 않는다 — 혼자 작업하고 배포 대상이 없어서 머지 단계만 늘어난다. 같이 작업하는 사람이 생기거나 릴리즈 전 QA 게이트가 실제로 필요해지면 그때 재검토한다.

```
main (트렁크, 항상 녹색)
 ├── jeho/ty-8-task-definition   → PR → squash merge → main
 ├── jeho/ty-9-ty-msgs           → PR → squash merge → main
 └── ...
릴리즈 프로젝트 완료 → annotated 태그(v0, v1 …) + GitHub Release
```

| 단계 | 규칙 |
|---|---|
| 티켓 | [Linear 팀 TY](https://linear.app/jhl81094/team/TY)에서 관리. 릴리즈 = 프로젝트, epic = 부모 이슈, 스토리 = 하위 이슈 |
| 브랜치 | 티켓 하나 = 브랜치 하나. 이름은 Linear가 주는 `jeho/ty-<번호>-<slug>` 그대로 |
| 커밋 | Conventional Commits — `feat(teleop):` · `fix(sim):` · `docs:` · `chore:` · `test:` |
| PR | 본문에 `Fixes TY-<번호>`. 템플릿의 완료 조건 · 수치 · 확인 방법을 채운다 |
| 머지 | squash merge만. main은 선형 히스토리를 유지하고 머지된 브랜치는 삭제 |
| 릴리즈 | 태그 + Release 노트에 데모 영상 · 평가 조건표 수치 · 재현 절차를 첨부 |

릴리즈 노트가 이 프로젝트의 배포 산출물이다. "이 태그에서 이 명령을 실행하면 이 수치가 나온다"까지 적어, 각 릴리즈가 그 자체로 완결됐음을 확인할 수 있게 한다(설계 원칙 6).

## 검토했지만 채택하지 않은 기술

### Jev / TypeSafe System One 모델 (2026-09 검토)

텍스트로 표현된 프로그램 상태 + 타입이 붙은 질문을 받아 이산 결정(Choice / Score / Noul)을 70–500ms에 반환하는 클라우드 모델. "게임 · 로봇 · 시뮬레이션 같은 실시간 루프"를 타깃으로 홍보한다.

**채택하지 않은 이유:**

1. **입출력 타입이 안 맞는다 — 속도 문제가 아니다.** 제어 계층은 20ms마다 연속 실수 6개를 요구하고 정책 계층은 이미지를 입력으로 받는다. Jev는 연속값을 뱉지 못하고 이미지를 받지 못한다. 응답이 1ms여도 꽂히는 구멍이 아니다.
2. **태스크 레벨 결정 계층이 없다.** Jev가 맞는 자리는 "다음에 어떤 스킬을 실행할까" 같은 초 단위 이산 판단인데, 단일 pick-and-place에는 그 계층이 존재하지 않는다.
3. **v4 RL 보상 자리는 타입이 맞지만 필요가 없다.** `Score(state) → 0~1`은 보상 함수 시그니처와 같고 상태가 숫자라 비전도 필요 없다. 다만 시뮬에서는 물체 pose가 ground truth로 나오므로 기하 계산 몇 줄이 더 빠르고 결정적이며 재현 가능하다(설계 원칙 3).
4. **클라우드 전용 + 얼리액세스.** 온보드 추론 원칙과 충돌하고, 공개 직후라 크리티컬 패스에 두기에 이르다.

**재검토 조건** (하나라도 성립하면):

- 태스크가 멀티스텝으로 확장되어 "다음 스킬 선택" 판단이 실제로 생길 때 (v5)
- v4에서 **해석적으로 짜기 어려운 보상**(파지 안정성 · 동작의 자연스러움 · 불필요한 우회 여부)이 병목이 될 때. 이 경우에도 학습 루프에서 직접 호출하지 않고 **오프라인으로 에피소드를 라벨링 → 로컬 보상 네트워크로 증류 → RL 루프는 로컬로 풀스피드** 형태를 쓴다.
- 비전 입력을 지원해서 v3 실물 평가의 **실패 모드 분류**(파지 실패 / 놓침 / 위치 오차 / 추론 지연 / 동역학 갭)에 쓸 수 있게 될 때

### 모바일 매니퓰레이터 (팔 + 바퀴 베이스)

베이스와 적재 사양 때문에 하드웨어 비용이 두 배 가까이 늘고, Nav2 학습에만 3–4주가 추가된다. 더 큰 문제는 바퀴 미끄러짐과 오도메트리 드리프트가 팔 오차 위에 누적되어 sim2real 갭이 곱셈으로 커지고, 로봇 위치까지 리셋해야 해서 평가 재현성(설계 원칙 3)이 깨진다는 점이다. **태스크 다양성이 목적이라면 고정팔 멀티스텝 태스크가 추가 비용 0원으로 같은 효과를 낸다** (v5).

## 리스크

- **ROS 2 · 로봇 도메인 학습 곡선** — v0에서 새로 배우는 게 가장 많다. v0가 2주 이상 초과되면 IK 텔레오퍼레이션 대신 스크립트 시연(planner)으로 데이터를 만들어 v1으로 넘어간다.
- **시뮬 텔레오퍼레이션 데이터 품질** — 게임패드 시연은 사람 손 시연보다 거칠다. 데이터 검증 규칙과 필터링으로 대응하고, 이 차이 자체를 v3에서 수치로 비교한다.
- **실물 하드웨어** — 조립 · 캘리브레이션 · 배송 지연. v2 시작 시 주문해 v3 전에 도착하게 한다. 서보는 캘리브레이션 실수로 태우기 쉬우므로 예비를 함께 산다.
- **RL 보상 해킹** — RL 정책이 MuJoCo 물리의 빈틈을 파고들어 시뮬 점수만 올리고 실물에서 무너질 수 있다. v4를 v3 뒤에 두는 이유가 이것이고, 실물 재평가가 검증 장치다.
- **RL 보상 설계 시간** — v4가 2주를 초과하면 residual RL을 접고 "실패 에피소드 재수집 → BC 재학습"(DAgger 계열)으로 대체한 뒤 v5로 넘어간다. 목표는 RL 자체가 아니라 "IL 위에 개선 루프를 얹는 경험"이다.

---

문서 사이트: <https://jhl8109.github.io/trainyard/>

개발 환경 셋업: [`docs/SETUP.md`](docs/SETUP.md)
