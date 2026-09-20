"""E2 · MuJoCo 씬 — MJCF 조립 · 로딩 · 도달성 측정 (TY-13 ~).

ROS 2 없이 돌아야 하는 코드다. 시뮬 브리지 노드(`ty_sim`)도, 평가 하네스도, v4 RL도
같은 모델을 여기서 얻는다 — 씬이 갈라지면 "같은 조건에서 비교한다"가 깨진다.
"""

from trainyard.sim.scene import (
    ARM_JOINTS,
    CAMERAS,
    JOINTS,
    OBJECT_BODY,
    TARGET_ZONE_SITE,
    TIP_SITE,
    check_mjx_constraints,
    load_model,
    menagerie_dir,
    scene_xml,
    write_scene,
)

__all__ = [
    "ARM_JOINTS",
    "CAMERAS",
    "JOINTS",
    "OBJECT_BODY",
    "TARGET_ZONE_SITE",
    "TIP_SITE",
    "check_mjx_constraints",
    "load_model",
    "menagerie_dir",
    "scene_xml",
    "write_scene",
]
