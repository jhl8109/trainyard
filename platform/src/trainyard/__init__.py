"""TrainYard 플랫폼 — ROS 2 런타임 바깥에서 도는 코드.

서브패키지 경계는 Linear epic과 1:1로 맞춘다:

- :mod:`trainyard.data` — E5 데이터 파이프라인
- :mod:`trainyard.policies` — 정책 구현 (BC · ACT · residual)
- :mod:`trainyard.training` — 학습 러너
- :mod:`trainyard.evaluation` — E7 평가 하네스
- :mod:`trainyard.api` — E8 잡 큐 · FastAPI
"""

__version__ = "0.0.0"
