"""pick-and-place 씬과 태스크 config가 서로 어긋나지 않는지 본다 (TY-13).

여기서 잡으려는 것은 두 가지다.

1. **씬이 MJX 제약을 깬다** — 충돌 메시 · equality · tendon (docs/task-pick-place.md §8).
   v4에서 GPU로 옮길 때 드러나면 그때는 씬을 다시 만들어야 한다.
2. **config와 씬이 갈라진다** — 테이블·목표 존 수치는 MJCF와 `config/task/pick_place.yaml`
   두 곳에 있고, 한쪽만 고치면 평가(TY-44)와 씬 리셋(TY-17)이 다른 세계를 보게 된다.

MuJoCo나 mujoco_menagerie가 없는 환경에서는 통째로 skip 한다 — 이 테스트가 ROS·GPU
없는 CI에서도 도는 것이 목적이지, 모델을 CI에 번들하는 것이 목적이 아니다.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "config" / "task" / "pick_place.yaml"

mujoco = pytest.importorskip("mujoco")
yaml = pytest.importorskip("yaml")


@pytest.fixture(scope="module")
def model():
    from trainyard.sim import load_model, menagerie_dir

    try:
        menagerie_dir()
    except FileNotFoundError as exc:
        pytest.skip(str(exc))
    return load_model()


@pytest.fixture(scope="module")
def config():
    return yaml.safe_load(CONFIG.read_text())


def geom_size(model, name):
    gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
    assert gid >= 0, f"geom {name} 없음"
    return model.geom_pos[gid], model.geom_size[gid]


def test_model_loads_with_expected_dofs(model):
    from trainyard.sim import JOINTS

    names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i) for i in range(model.njnt)
    ]
    assert names[: len(JOINTS)] == list(JOINTS), "관절 순서가 액션 벡터 순서와 다르다"
    assert model.nu == len(JOINTS), "액추에이터는 팔 5 + 그리퍼 1"
    assert model.nq == len(JOINTS) + 7, "물체 freejoint 7개가 빠졌다"


def test_cameras_present(model):
    from trainyard.sim import CAMERAS

    names = {
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_CAMERA, i) for i in range(model.ncam)
    }
    assert set(CAMERAS) <= names


def test_mjx_constraints(model):
    """docs §8 — 충돌 geom은 primitive만, equality · tendon 금지."""
    from trainyard.sim import check_mjx_constraints

    violations = check_mjx_constraints(model)
    assert not violations, violations


def test_object_and_pad_contacts_are_explicit_pairs(model):
    """그리퍼 패드–물체 마찰은 <pair>로 명시한다 (docs §8)."""
    cube = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "cube")
    pairs = [
        i
        for i in range(model.npair)
        if cube in (model.pair_geom1[i], model.pair_geom2[i])
    ]
    assert pairs, "물체–패드 contact pair가 없다"
    for i in pairs:
        assert model.pair_friction[i][0] > 0


def test_home_keyframe_starts_out_of_collision(model):
    """home 자세에서 팔이 테이블·물체를 뚫고 있으면 리셋(TY-17)이 튄다."""
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, data, 0)
    mujoco.mj_forward(model, data)

    cube = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "cube")
    table = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "table")
    for con in data.contact[: data.ncon]:
        assert {con.geom1, con.geom2} == {cube, table}, (
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, con.geom1),
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, con.geom2),
        )


def test_scene_is_stable_without_control(model):
    """제어 없이 2초를 굴려도 발산하지 않는다."""
    import numpy as np

    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, data, 0)
    data.ctrl[:] = model.key_ctrl[0]
    for _ in range(int(2.0 / model.opt.timestep)):
        mujoco.mj_step(model, data)
    assert np.isfinite(data.qpos).all()
    cube = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "cube")
    assert data.xpos[cube][2] == pytest.approx(0.0125, abs=2e-3), "큐브가 테이블을 뚫거나 떴다"


def test_config_matches_scene(model, config):
    """테이블·목표 존은 MJCF와 config 두 곳에 있다 — 두 값이 같아야 한다."""
    pos, size = geom_size(model, "table")
    assert (pos[0], pos[1]) == pytest.approx(tuple(config["table"]["center"]), abs=1e-9)
    assert (2 * size[0], 2 * size[1]) == pytest.approx(tuple(config["table"]["size"]), abs=1e-9)
    assert pos[2] + size[2] == pytest.approx(config["table"]["top_z"], abs=1e-9)

    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "target_zone")
    zone = config["target_zone"]
    assert tuple(model.site_pos[sid][:2]) == pytest.approx(tuple(zone["center"]), abs=1e-9)
    assert (2 * model.site_size[sid][0], 2 * model.site_size[sid][1]) == pytest.approx(
        tuple(zone["size"]), abs=1e-9
    )

    _, cube_size = geom_size(model, "cube")
    assert 2 * cube_size[0] == pytest.approx(config["object"]["size"], abs=1e-9)


def test_spawn_grid_is_inside_the_table_and_clear_of_the_zone(config):
    from trainyard.sim.reach import zone_blocked

    table, grid = config["table"], config["spawn_grid"]
    points = grid["A"] + grid["B_edge"] + grid["B_interp"]
    assert len(set(map(tuple, points))) == len(points), "A · B에 같은 지점이 중복됐다"

    half = (table["size"][0] / 2, table["size"][1] / 2)
    for x, y in points:
        assert abs(x - table["center"][0]) <= half[0]
        assert abs(y - table["center"][1]) <= half[1]
        assert not zone_blocked(
            x, y, zone=tuple(config["target_zone"]["center"]),
            size=tuple(config["target_zone"]["size"]),
            clearance=config["object"]["size"] / 2,
        ), f"({x}, {y})는 목표 존과 겹친다"


@pytest.mark.parametrize("group", ["A", "B_edge", "B_interp"])
def test_sampled_spawn_points_are_reachable(model, config, group):
    """config의 지점이 실제로 top-down으로 도달 가능한지 표본으로 다시 푼다.

    전수 스윕은 5초라 테스트에 넣지 않는다. 씬이 바뀌어 격자가 무효가 되면 대개
    영역 전체가 같이 틀어지므로, 양끝과 가운데 3점이면 회귀를 잡는다.
    """
    import numpy as np

    from trainyard.sim.reach import MARGIN_MIN, arm_index, best_ik

    points = config["spawn_grid"][group]
    data = mujoco.MjData(model)
    idx = arm_index(model)
    for x, y in (points[0], points[len(points) // 2], points[-1]):
        res = best_ik(model, data, idx, np.array([x, y, config["spawn_grid"]["grasp_z"]]))
        assert res.ok, f"({x}, {y}) IK 실패"
        assert res.margin >= MARGIN_MIN, f"({x}, {y}) 관절 여유 {res.margin:.3f}"
