# ty_bringup/launch

노드를 조합해 실행하는 launch 파일이 들어가는 자리. 예정된 진입점:

| 파일 | 띄우는 것 | 티켓 |
|---|---|---|
| `sim.launch.py` | MuJoCo 브리지 + 카메라 퍼블리시 | TY-14 · TY-15 |
| `teleop.launch.py` | `sim` + 게임패드 · IK · 에피소드 기록 | TY-19 ~ TY-24 |
| `eval.launch.py` | `sim` + 추론 노드 | TY-30 |

설정은 레포 루트 [`config/`](../../../../config/README.md) 한 곳에서 관리하고,
launch는 **경로를 인자로 넘기기만 한다**. 같은 파일을 `platform/`의 학습·평가 코드가 그대로 읽는다.
