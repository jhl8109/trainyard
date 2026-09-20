"""pick-and-place 씬 로딩 — MJCF 조립 · MJX 제약 점검 · 오프스크린 렌더 (TY-13).

ROS 2에 의존하지 않는다. 시뮬 브리지 노드(TY-14) · 평가 하네스 · v4 RL이 모두
이 모듈 하나로 같은 모델을 얻는다.

    from trainyard.sim import load_model
    model = load_model()

CLI:

    python -m trainyard.sim --check                 # 로드 + 수치 요약
    python -m trainyard.sim --render /tmp/top.png   # 오프스크린 렌더 (MUJOCO_GL=egl)
    python -m trainyard.sim --write /tmp/scene.xml  # 경로가 풀린 XML

GUI로 보려면 풀린 XML을 뷰어에 넘긴다 (헤드리스 세션에서는 안 된다):

    .venv/bin/python -m mujoco.viewer --mjcf=/tmp/scene.xml
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MODEL_XML = Path(__file__).resolve().parent / "models" / "pick_place.xml"

#: 팔 관절 5개 + 그리퍼 1개. 순서가 joint_states · 액션 벡터의 순서다 (docs §1).
ARM_JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll")
GRIPPER_JOINT = "gripper"
JOINTS = (*ARM_JOINTS, GRIPPER_JOINT)

#: 그리퍼 끝단 site. 로컬 +x가 파지 접근 축(top-down에서 월드 -z)이다.
TIP_SITE = "gripperframe"
APPROACH_AXIS = 0  # site_xmat의 열 인덱스

OBJECT_BODY = "cube"
TARGET_ZONE_SITE = "target_zone"
CAMERAS = ("top_cam", "wrist_cam")

_DEFAULT_MENAGERIE = Path.home() / "orca" / "mujoco_menagerie"


def menagerie_dir() -> Path:
    """mujoco_menagerie 체크아웃 경로. `MENAGERIE` 환경변수로 덮어쓴다."""
    path = Path(os.environ.get("MENAGERIE", _DEFAULT_MENAGERIE)).expanduser()
    if not (path / "robotstudio_so101" / "so101.xml").is_file():
        raise FileNotFoundError(
            f"mujoco_menagerie의 robotstudio_so101을 찾지 못했다: {path}. "
            "MENAGERIE 환경변수로 경로를 지정한다 (docs/SETUP.md)."
        )
    return path


def scene_xml(menagerie: Path | None = None) -> str:
    """`@MENAGERIE@`가 실제 경로로 치환된 MJCF 문자열."""
    root = Path(menagerie) if menagerie is not None else menagerie_dir()
    return MODEL_XML.read_text().replace("@MENAGERIE@", str(root))


def write_scene(dest: Path, menagerie: Path | None = None) -> Path:
    """경로가 풀린 XML을 파일로 쓴다. `simulate`(GUI) 뷰어에 그대로 넘길 수 있다."""
    dest = Path(dest)
    dest.write_text(scene_xml(menagerie))
    return dest


def load_model(menagerie: Path | None = None, mjx_safe: bool = True):
    """컴파일된 `mujoco.MjModel`.

    `mjx_safe`면 업스트림 팔 모델이 들고 있는 **메시 충돌 geom을 끈다.** 같은 자리에
    primitive(box · sphere · capsule) 충돌 geom이 이미 있어서 파지 접촉은 유지되고,
    "충돌 geom은 primitive만"(docs §8)이 컴파일된 모델 수준에서 성립한다. 업스트림
    XML을 포크하지 않고 여기서 끄는 이유는, 포크하면 캘리브레이션 업데이트를 매번
    따라가야 하기 때문이다. XML 레벨의 항구적 처리는 TY-105에서 정한다.
    """
    import mujoco

    model = mujoco.MjModel.from_xml_string(scene_xml(menagerie))
    if mjx_safe:
        disable_mesh_collisions(model)
    return model


def disable_mesh_collisions(model) -> int:
    """충돌에 참여하는 메시 geom을 시각 전용으로 돌린다. 끈 개수를 돌려준다."""
    import mujoco

    n = 0
    for i in range(model.ngeom):
        if model.geom_type[i] != mujoco.mjtGeom.mjGEOM_MESH:
            continue
        if model.geom_contype[i] or model.geom_conaffinity[i]:
            model.geom_contype[i] = 0
            model.geom_conaffinity[i] = 0
            n += 1
    return n


@dataclass(frozen=True)
class MjxViolations:
    """MJX 호환을 깨는 요소들 (docs/task-pick-place.md §8). 비어 있으면 통과."""

    equality: int
    tendon: int
    mesh_collision_geoms: tuple[str, ...]

    def __bool__(self) -> bool:
        return bool(self.equality or self.tendon or self.mesh_collision_geoms)


def check_mjx_constraints(model) -> MjxViolations:
    import mujoco

    bad = []
    for i in range(model.ngeom):
        if model.geom_type[i] == mujoco.mjtGeom.mjGEOM_MESH and (
            model.geom_contype[i] or model.geom_conaffinity[i]
        ):
            bad.append(mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) or f"geom{i}")
    return MjxViolations(int(model.neq), int(model.ntendon), tuple(bad))


def _summary(model) -> dict:
    import mujoco

    return {
        "nq": int(model.nq),
        "nv": int(model.nv),
        "nu": int(model.nu),
        "nbody": int(model.nbody),
        "ngeom": int(model.ngeom),
        "njnt": int(model.njnt),
        "ncam": int(model.ncam),
        "timestep": float(model.opt.timestep),
        "joints": [
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i) for i in range(model.njnt)
        ],
        "cameras": [
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_CAMERA, i) for i in range(model.ncam)
        ],
    }


def _main(argv=None) -> int:
    import argparse
    import time

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", type=Path, help="오프스크린 렌더 PNG 경로")
    parser.add_argument("--camera", default="top_cam", help="렌더 카메라 (기본 top_cam)")
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--write", type=Path, help="경로가 풀린 XML을 여기에 쓴다")
    parser.add_argument("--steps", type=int, default=0, help="렌더 전에 굴릴 물리 스텝")
    parser.add_argument("--check", action="store_true", help="수치 요약과 MJX 제약 점검")
    args = parser.parse_args(argv)

    import mujoco

    if args.write:
        print(write_scene(args.write))

    t0 = time.perf_counter()
    model = load_model()
    load_ms = (time.perf_counter() - t0) * 1e3
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, data, 0)
    mujoco.mj_forward(model, data)

    if args.check or not (args.render or args.write):
        for k, v in _summary(model).items():
            print(f"{k:10} {v}")
        print(f"{'load_ms':10} {load_ms:.1f}")
        print(f"{'mjx':10} {check_mjx_constraints(model)}")

    if args.steps:
        t0 = time.perf_counter()
        for _ in range(args.steps):
            mujoco.mj_step(model, data)
        wall = time.perf_counter() - t0
        sim = args.steps * model.opt.timestep
        print(f"{'step':10} {args.steps} steps, {wall*1e3:.0f}ms wall, {sim/wall:.0f}x realtime")

    if args.render:
        renderer = mujoco.Renderer(model, args.height, args.width)
        try:
            renderer.update_scene(data, camera=args.camera)
            img = renderer.render()
        finally:
            renderer.close()  # 명시적 close 없이 GC에 맡기면 종료 시 EGLError가 난다
        from PIL import Image  # noqa: PLC0415

        Image.fromarray(img).save(args.render)
        print(f"{'render':10} {args.camera} {img.shape} mean={img.mean():.1f} -> {args.render}")
    return 0
