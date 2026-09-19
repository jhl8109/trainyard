# TrainYard

사족보행 로봇(Unitree Go1)의 지형 적응형 보행을 학습시키면서, 여러 로봇·태스크·알고리즘을 계속 얹어서 학습시킬 수 있는 시뮬레이션 트레이닝 인프라를 만드는 프로젝트.

이름 그대로 여러 학습(training) job이 큐에 들어와 워커에 배차되는 조차장(yard) 구조를 지향한다.

> 서버 개발 3년 차에서 로봇 시뮬레이션 엔지니어로 전환하기 위한 포트폴리오 프로젝트.

## 목표

RL 알고리즘 자체를 새로 고안하기보다는, 기존 알고리즘(PPO)을 내부까지 이해하고 정확히 쓰는 데 집중하고, 그 위에 태스크·알고리즘을 플러그인처럼 등록·실행·비교할 수 있는 플랫폼 레이어를 쌓는다. 서버 개발 경력(분산 시스템, API, 인프라)이 가장 직접적으로 재사용되는 지점이 이 플랫폼 레이어다.

## 설계 원칙

1. **RL 기본기는 생략하지 않는다.** 라이브러리를 쓰기 전에 CartPole에서 PPO를 밑바닥부터 구현한다.
2. **고정 태스크 + 자동 커리큘럼으로 "지속 개선"을 구현한다.** 평지 보행 baseline 위에 지형 난이도·물리 파라미터를 성공률 기반으로 자동 확장하는 커리큘럼(ADR)을 얹는다.
3. **플랫폼화를 우선하고, 컨테이너화는 완성 후 폴리싱 단계로 미룬다.**
4. **k8s는 쓰지 않는다.** 인터페이스는 수평 확장 가능하게 설계하되, 실행은 Docker Compose 수준으로 유지한다.
5. **모든 릴리즈는 그 자체로 완결되어야 한다.** v0~v3 각 단계가 독립적으로 완결된 상태를 유지한다.

## 아키텍처

```
Task Registry ─┐
                ├─> Training Job API ─> Job Queue ─> Worker Pool (MuJoCo/MJX, GPU 1개)
Algorithm Registry ┘                                       │
                                          ┌──────────────────┼───────────────────┐
                                          ▼                                      ▼
                                   Experiment DB                          Model Registry
                                          │
                                          ▼
                                     Dashboard
```

## 로드맵

| 릴리즈 | 범위 | 기간 | 상태 |
|---|---|---|---|
| v0 | RL 기본기(PPO 밑바닥 구현) + Go1 평지 보행 baseline + 보상곡선 대시보드 | 4–5주 | 다음 시작 |
| v1 | 지형 커리큘럼 + ADR 레이어 | +2주 | 계획 |
| v2 | Job Queue 기반 플랫폼 core (Task/Algorithm Registry, Training Job API, 실험 관리 백엔드) | +3주 | 계획 |
| v3 (선택) | 2번째 태스크(로봇팔) 추가 + Registry 리팩터링 + Model Registry + Docker 폴리싱 + CI/CD | +4주 | 여력 시 |

## 기술 스택

| 영역 | 선택 |
|---|---|
| 물리 시뮬레이션 | MuJoCo / MJX (JAX) |
| RL 라이브러리 | Stable-Baselines3, 필요 시 RSL-RL |
| Job Queue | Ray 또는 Redis + Celery |
| Backend API | FastAPI |
| 실험 메타데이터 | PostgreSQL |
| 컨테이너화 | Docker (v3 폴리싱 단계) |
| 대시보드 | 웹 프론트(React 또는 경량 스택) |

## 하드웨어

- CPU: AMD Ryzen 5 5600 (6C/12T)
- GPU: RTX 4060 Ti
- RAM: 32GB
- OS: Linux Mint 22.3

## 리스크 & 확장

- RL 디버깅은 시간 예측이 어렵다 — v0가 2주 이상 초과되면 baseline 난이도를 낮춰서라도 완결 상태를 우선한다.
- GPU 1장 제약은 설계 문서화로 상쇄한다 — 왜 이 설계가 멀티 GPU/멀티 노드로 옮겨질 수 있는지 명시적으로 서술한다.
- v3(플랫폼화)는 보너스다 — 취업 준비 일정과 겹치면 과감히 미루거나 스킵한다.

---

전체 설계 문서: [TrainYard Design Doc](https://claude.ai/code/artifact/ab5f744b-d543-4bc2-b95e-14be463ee00c)
