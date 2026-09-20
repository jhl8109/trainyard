# TrainYard — 작업 규약

로봇팔 모방학습 시스템. 텔레오퍼레이션 → 데이터 파이프라인 → 학습 → 평가 → 실시간 추론을 ROS 2 위에서 하나의 시스템으로 만든다. MuJoCo에서 완성하고 같은 인터페이스로 실물 SO-101(v3)로 옮긴 뒤 residual RL(v4)을 얹는다.

## 먼저 읽을 것

| 문서 | 무엇이 있나 |
|---|---|
| `README.md` | 설계 원칙 · 아키텍처 · 로드맵 · 개발 워크플로 · 채택하지 않은 기술 |
| `docs/task-pick-place.md` | 태스크 정의. 성공 판정 · 실패 모드 · 평가 조건표 · 보상 구조의 **단일 출처** |
| `docs/SETUP.md` | 환경 구성과 실측 결과 |

숫자(성공 기준·조건표·보상 항)가 필요하면 추측하지 말고 `docs/task-pick-place.md`를 읽는다. 그 문서에 없으면 "측정 후 확정" 항목이므로 어느 티켓에서 정하는지 확인한다.

## 세션 단위

**세션 1개 = 티켓 1개 = 워크트리 1개 = PR 1개.** 끝나면 세션을 버린다. 남는 것은 PR과 Linear 코멘트뿐이므로, 다음 세션이 알아야 할 것은 전부 거기에 적는다.

티켓이 예상보다 커지면 세션을 늘리지 말고 하위 이슈로 쪼갠다: `scripts/ty.py sub TY-14 "제목"`.

## 작업 관리 — Linear (팀 TY)

```bash
python3 scripts/ty.py next            # 작업 가능한 큐 (릴리즈 → 번호 순)
python3 scripts/ty.py show TY-14      # 본문 + 코멘트 (결정 이력이 코멘트에 있다)
python3 scripts/ty.py epic TY-12      # epic 하위 진행 상황
python3 scripts/ty.py state TY-14 "In Progress"
python3 scripts/ty.py comment TY-14 "..."
python3 scripts/ty.py label TY-14 needs/decision
```

릴리즈 = 프로젝트, epic = 부모 이슈, 스토리 = 하위 이슈. epic은 직접 작업하지 않는다(큐에서 제외된다).

## 브랜치 · PR

```bash
bash scripts/worktree.sh ls                            # 다른 세션이 뭘 잡고 있는지 먼저 본다
bash scripts/worktree.sh add TY-14 sim-bridge-node     # 언제나 main에서
bash scripts/worktree.sh prune                         # 머지된 워크트리 정리 (-y: 커밋 0개인 것까지)
```

- **브랜치는 전부 `main`에서 딴다.** `ty.py next`가 epic마다 아직 안 끝난 가장 낮은 번호 하나만 내보내므로, 큐에 나온 티켓은 선행 티켓이 이미 `Done`이다. 쌓을 일이 없으니 리베이스도 없다. `--on`은 사람이 직접 지시했을 때만 쓰는 예외 탈출구고 깊이 1을 넘기지 않는다
- 브랜치 이름은 `<사용자>/ty-<번호>-<slug>` 꼴이면 된다. 티켓 연결은 브랜치 이름이 아니라 **PR 본문의 `Fixes TY-<번호>`**가 한다
- **여러 세션이 동시에 돈다.** 워크트리를 만들기 전에 `worktree.sh ls`로 같은 티켓을 잡고 있는지 확인한다(스크립트가 중복이면 막는다). 커밋할 때 `git add -A`를 쓰지 않는다 — 다른 세션이 만든 파일이 섞인다
- 커밋은 Conventional Commits, 본문에 **왜 이 방식인지** 한두 줄
- PR 본문은 `.github/pull_request_template.md`를 채운다. `Fixes TY-<번호>` 필수
- `main` 직접 push 금지(ruleset). squash merge만
- **머지는 사람이 한다.** PR을 올리고 `In Review`로 바꾼 뒤 세션을 끝낸다. 머지되면 Linear가 티켓을 `Done`으로 바꾸고, 그때 같은 epic의 다음 티켓이 큐에 열린다 — **큐가 비면 할 일이 없는 게 아니라 머지 대기다**

## 명령

```bash
pytest                                 # 플랫폼 (ROS 불필요, testpaths=platform/tests)

source /opt/ros/jazzy/setup.bash       # ros2 · rclpy 쓰기 전 항상
cd ros2_ws && colcon build && colcon test

.venv/bin/python                       # torch · mujoco · lerobot (워크트리에서는 심볼릭 링크)
bash scripts/verify_env.sh             # 환경 검증 (재부팅 후 · 의존성 바꾼 뒤)
```

코드를 어디에 둘지는 README `레포 구조`를 따른다. 기준은 하나다 — **ROS 2를 source 해야 돌아가는 코드만 `ros2_ws/`에 둔다.** 학습 · 평가 · API는 로봇 없이 돌아야 하므로 `platform/src/trainyard/`에 남는다.

의존성을 추가할 때는 레포 루트 `requirements.txt`(고정 버전의 단일 출처)에 넣는다. `platform/pyproject.toml`에는 런타임 의존성을 적지 않는다.

## 묻지 말고 해도 되는 것

구현 · 테스트 작성 · 리팩터 · 파일 생성 · 커밋 · 브랜치 push · PR 생성 · Linear 상태·코멘트 갱신 · 측정 실행 · 워크트리 생성 · 머지된 워크트리 정리(`prune`).

`git add -A` · `git commit -a` · `git push --force` · `main` 직접 push는 `.claude/hooks/guard.py`가 차단한다. 산문으로 부탁하지 않고 훅으로 막는 이유는 여러 세션이 같은 레포에서 동시에 돌기 때문이다.

## 반드시 사람에게 넘기는 것

1. **`type/spike` 티켓과 설계 변경** — 태스크 정의 · 평가 조건표 · 인터페이스 계약의 숫자를 바꾸는 결정. 근거를 정리해 제시하고 멈춘다
2. **PR 머지** — 올리기까지만 한다
3. **돈 쓰기 · 레포 설정 · 외부 공개** — 하드웨어 주문, GitHub 설정 변경, 공개 범위 변경

막히면 진행하지 말고 `needs/decision` 라벨 + 무엇이 왜 막혔는지 코멘트를 남기고 끝낸다.

## 세션 종료 시 남길 것

1. PR 링크와 `Fixes TY-<번호>`
2. Linear 코멘트 — 내린 결정, 측정 수치, 다음 티켓이 알아야 할 것. 다른 티켓에 영향이 가면 그 티켓에도 코멘트
3. 티켓 상태 `In Review`
4. 사용자에게 3줄 요약: 무엇을 했나 / 수치 / 다음에 필요한 결정

## 이 프로젝트의 문화

- **수치가 없으면 완료가 아니다.** 측정이 필요한 티켓은 PR 본문 "수치/근거"를 채운다. 성공률은 신뢰구간과 함께, 지연은 p50/p99로
- **재현 가능해야 한다.** 랜덤 시드 · config 해시 · 데이터셋 버전을 기록한다. 조건표 없이 "잘 되는 것 같다"는 근거가 아니다
- **시뮬과 실물은 같은 인터페이스를 쓴다.** 하드웨어 계층 밖에서 시뮬 여부를 분기하지 않는다
- **MJX 호환을 깨지 않는다.** 충돌 geom은 primitive만, equality constraint · tendon 금지 (`docs/task-pick-place.md` §8)
- **평가 성공 판정은 순수 함수다.** ROS 2 · MuJoCo에 의존하지 않는다. v4 RL 보상이 같은 함수를 쓴다

## 공개 레포 주의

공개 레포다. 커리어 목표 · 타깃 회사 · 연봉 · 구직 일정은 커밋하지 않는다. 그런 맥락은 `docs/internal/`(gitignore) 또는 비공개 설계 문서에만 둔다.
