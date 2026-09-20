# config/

ROS 2 런타임(`ros2_ws/`)과 플랫폼 코드(`platform/`)가 **같은 파일을 읽는** 설정만 여기에 둔다.

| 파일 | 내용 | 쓰는 곳 | 만드는 티켓 |
|---|---|---|---|
| `task/pick_place.yaml` | 물체 스폰 격자 · 목표 존 · 성공 판정 파라미터 · seed 지터 | 씬 리셋(TY-17) · 평가 조건표(TY-44) · RL 보상(TY-111) | TY-13 |

`task/pick_place.yaml`은 **생성물이다.** 격자는 MuJoCo 모델에 top-down IK를 풀어 얻으므로
손으로 고치면 씬과 어긋난다. 씬(`platform/src/trainyard/sim/models/pick_place.xml`)을
바꿨으면 다시 돌린다:

```bash
PYTHONPATH=platform/src .venv/bin/python -m trainyard.sim.reach --out config/task/pick_place.yaml
```

스윕은 결정적이라 모델이 그대로면 같은 파일이 나온다. `platform/tests/test_sim_scene.py`가
씬과 이 파일의 테이블 · 목표 존 수치가 어긋나면 실패시킨다.

근거와 확정된 수치는 [`docs/task-pick-place.md`](../docs/task-pick-place.md)에 있다.

학습·평가 코드가 ROS 워크스페이스를 source 하지 않고도 같은 파일을 읽어야 하므로,
설정은 여기 한 곳에서 관리하고 노드에는 **launch 인자로 경로를 넘긴다.**
