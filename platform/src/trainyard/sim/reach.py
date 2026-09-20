"""도달성 스윕 — 평가 격자를 측정으로 확정한다 (docs/task-pick-place.md §6, TY-13).

절차는 문서 §6 그대로다.

1. 테이블 작업 영역을 20mm 격자로 나눈다.
2. 각 셀 중심에 top-down 파지 자세(그리퍼 수직, z = 물체 중심 높이)로 IK를 푼다.
3. 해가 있고 관절 한계에서 10% 이상 여유가 있는 셀만 후보로 남긴다.
4. 후보 영역 경계에서 10mm 안쪽으로 줄인 뒤 학습 분포 A(안쪽 60%)와 held-out B로 나눈다.
5. 결과를 `config/task/pick_place.yaml`로 커밋한다.

IK는 감쇠 최소자승(DLS)이다. SO-101은 팔 5-DoF라 위치 3 + 접근축 수직 2 = 5 구속이
정확히 결정되고, 그리퍼 yaw는 `wrist_roll`이 남은 자유도로 자유롭게 잡는다 — 그래서
스윕은 yaw를 구속하지 않는다(§1의 top-down 파지 정의와 같다).

    python -m trainyard.sim.reach --out config/task/pick_place.yaml
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from trainyard.sim.scene import APPROACH_AXIS, ARM_JOINTS, TIP_SITE

#: IK 수렴 판정. 위치 0.5mm · 접근축 정렬 오차 sin θ < 1e-3 (≈ 0.06°).
POS_TOL = 5e-4
ROT_TOL = 1e-3

#: 관절 한계 여유 기준 — (한계까지 거리 / 가동범위)의 최솟값 (§6 3단계).
MARGIN_MIN = 0.10

#: 시드 자세. 팔꿈치 위/아래 해가 둘 다 있어서 하나만 쓰면 도달 영역을 과소평가한다.
SEED_POSES = (
    (0.0, 0.0, 0.0, 0.0, 0.0),
    (0.0, -0.6, 1.2, 1.0, 0.0),
    (0.0, 0.6, -1.2, -1.0, 0.0),
    (0.0, -1.2, 1.5, 0.8, 0.0),
)


@dataclass(frozen=True)
class ArmIndex:
    """IK가 건드리는 팔 관절의 인덱스와 한계."""

    qadr: np.ndarray
    dofadr: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    site: int

    @property
    def span(self) -> np.ndarray:
        return self.hi - self.lo


def arm_index(model) -> ArmIndex:
    import mujoco

    jids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n) for n in ARM_JOINTS]
    return ArmIndex(
        qadr=np.array([model.jnt_qposadr[j] for j in jids]),
        dofadr=np.array([model.jnt_dofadr[j] for j in jids]),
        lo=model.jnt_range[jids, 0].copy(),
        hi=model.jnt_range[jids, 1].copy(),
        site=mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, TIP_SITE),
    )


@dataclass
class IkResult:
    q: np.ndarray
    pos_err: float
    rot_err: float
    ok: bool
    iters: int
    margin: float = field(default=0.0)


def solve_top_down(model, data, idx: ArmIndex, target, q0, *, iters=200, damping=1e-3, step_max=0.3):
    """접근축을 월드 -z로 세운 채 `target`(팔 끝단 site 위치)에 도달하는 관절각.

    yaw는 구속하지 않는다 — 접근축 정렬은 외적 하나로 표현되고 이 잔차는 랭크 2다.
    """
    import mujoco

    q = np.clip(np.asarray(q0, dtype=float).copy(), idx.lo, idx.hi)
    jacp = np.zeros((3, model.nv))
    jacr = np.zeros((3, model.nv))
    down = np.array([0.0, 0.0, -1.0])
    pos_err = rot_err = float("inf")

    for it in range(iters):
        data.qpos[idx.qadr] = q
        mujoco.mj_kinematics(model, data)
        mujoco.mj_comPos(model, data)

        e_pos = target - data.site_xpos[idx.site]
        approach = data.site_xmat[idx.site].reshape(3, 3)[:, APPROACH_AXIS]
        e_rot = np.cross(approach, down)
        pos_err = float(np.linalg.norm(e_pos))
        rot_err = float(np.linalg.norm(e_rot))
        if pos_err < POS_TOL and rot_err < ROT_TOL:
            return IkResult(q, pos_err, rot_err, True, it)

        mujoco.mj_jacSite(model, data, jacp, jacr, idx.site)
        jac = np.vstack([jacp[:, idx.dofadr], jacr[:, idx.dofadr]])
        err = np.concatenate([e_pos, e_rot])
        dq = jac.T @ np.linalg.solve(jac @ jac.T + damping * np.eye(6), err)
        norm = np.linalg.norm(dq)
        if norm > step_max:
            dq *= step_max / norm
        q = np.clip(q + dq, idx.lo, idx.hi)

    return IkResult(q, pos_err, rot_err, False, iters)


def joint_margin(idx: ArmIndex, q: np.ndarray) -> float:
    """관절 한계까지 남은 여유를 가동범위로 정규화한 값의 최솟값."""
    return float(np.min(np.minimum(q - idx.lo, idx.hi - q) / idx.span))


def best_ik(model, data, idx: ArmIndex, target) -> IkResult:
    """시드를 모두 풀어 여유가 가장 큰 해를 고른다."""
    best = None
    for seed in SEED_POSES:
        q0 = np.array(seed, dtype=float)
        # 첫 관절은 목표 방위각으로 시작한다 — 반대편으로 도는 해에 빠지지 않는다.
        q0[0] = np.clip(np.arctan2(target[1], target[0]), idx.lo[0], idx.hi[0])
        res = solve_top_down(model, data, idx, target, q0)
        if not res.ok:
            continue
        res.margin = joint_margin(idx, res.q)
        if best is None or res.margin > best.margin:
            best = res
    return best or IkResult(np.zeros(len(ARM_JOINTS)), float("inf"), float("inf"), False, 0)


def grid_axis(center: float, size: float, pitch: float) -> np.ndarray:
    """`size` 폭 구간을 `pitch` 간격 셀로 나눈 셀 중심들 (양끝은 반 칸 안쪽)."""
    n = int(round(size / pitch))
    start = center - size / 2 + pitch / 2
    return np.round(start + pitch * np.arange(n), 6)


def sweep(model, xs, ys, grasp_z: float, margin_min: float = MARGIN_MIN) -> dict:
    """격자 전체를 풀어 셀별 (해 존재, 여유)를 돌려준다."""
    import mujoco

    data = mujoco.MjData(model)
    idx = arm_index(model)
    solved: dict[tuple[int, int], IkResult] = {}
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            res = best_ik(model, data, idx, np.array([x, y, grasp_z]))
            if res.ok:
                solved[(i, j)] = res
    candidates = {k: r for k, r in solved.items() if r.margin >= margin_min}
    return {"solved": solved, "candidates": candidates}


def erode(cells: set[tuple[int, int]]) -> set[tuple[int, int]]:
    """4-이웃이 모두 후보인 셀만 남긴다.

    셀 중심 사이 간격이 20mm이므로, 이웃이 빈 셀은 후보 영역 경계에서 10mm 안쪽에
    있다. 그 셀을 버리는 것이 §6 4단계의 "경계에서 10mm 안쪽으로 줄인다"이다.
    """
    return {c for c in cells if all((c[0] + di, c[1] + dj) in cells for di, dj in
                                    ((1, 0), (-1, 0), (0, 1), (0, -1)))}


def depth_map(cells: set[tuple[int, int]]) -> dict[tuple[int, int], int]:
    """각 셀이 영역 경계에서 몇 칸 안쪽인지 (체비셰프 거리 기준 침식 깊이)."""
    depth = {}
    remaining = set(cells)
    layer = 1
    while remaining:
        edge = {
            c
            for c in remaining
            if any(
                (c[0] + di, c[1] + dj) not in remaining
                for di in (-1, 0, 1)
                for dj in (-1, 0, 1)
                if (di, dj) != (0, 0)
            )
        }
        for c in edge:
            depth[c] = layer
        remaining -= edge
        layer += 1
    return depth


def split_ab(cells: set[tuple[int, int]], inner_ratio: float = 0.6):
    """안쪽 `inner_ratio`를 학습 분포 A로, 나머지 바깥 테두리를 held-out B로 나눈다.

    경계로부터의 깊이 순으로 자른다 — A가 연결된 안쪽 덩어리가 되고 B가 그 둘레의
    테두리가 되어, "학습 분포 밖"이라는 말이 기하적으로 성립한다.
    """
    depth = depth_map(cells)
    target = int(round(len(cells) * inner_ratio))
    # 깊이가 깊은 셀부터 A에 넣되, 같은 깊이는 통째로 넣는다(테두리가 끊기지 않게).
    by_depth: dict[int, list] = {}
    for c, d in depth.items():
        by_depth.setdefault(d, []).append(c)
    a: set[tuple[int, int]] = set()
    for d in sorted(by_depth, reverse=True):
        if a and len(a) + len(by_depth[d]) > target:
            break
        a |= set(by_depth[d])
    return a, set(cells) - a


# --- config/task/pick_place.yaml 생성 -------------------------------------------------

#: 스윕이 도는 격자. 테이블 크기는 씬(pick_place.xml)과 같아야 한다.
TABLE_CENTER = (0.17, 0.0)
TABLE_SIZE = (0.30, 0.40)
GRID_PITCH = 0.02
GRASP_Z = 0.0125  # 25mm 큐브의 중심 높이 (docs §2)
ZONE_CENTER = (0.10, 0.15)
ZONE_SIZE = (0.08, 0.08)
INNER_RATIO = 0.6


def zone_blocked(x: float, y: float, *, zone=ZONE_CENTER, size=ZONE_SIZE, clearance: float = 0.0125) -> bool:
    """목표 존과 겹치는 스폰 지점인가.

    존 안에서 시작하면 집기 전에 이미 `placed`라 에피소드가 공짜로 성공한다. 물체
    반폭(12.5mm)만큼 더 띄워서 걸치는 경우까지 뺀다.
    """
    return (
        abs(x - zone[0]) <= size[0] / 2 + clearance
        and abs(y - zone[1]) <= size[1] / 2 + clearance
    )


def build_grid(model, *, pitch=GRID_PITCH, grasp_z=GRASP_Z, margin_min=MARGIN_MIN,
               inner_ratio=INNER_RATIO) -> dict:
    """§6 1~4단계를 돌려 A · B 지점과 중간 수치를 돌려준다."""
    import mujoco

    xs = grid_axis(TABLE_CENTER[0], TABLE_SIZE[0], pitch)
    ys = grid_axis(TABLE_CENTER[1], TABLE_SIZE[1], pitch)
    result = sweep(model, xs, ys, grasp_z, margin_min)
    candidates = set(result["candidates"])
    eroded = erode(candidates)
    usable = {c for c in eroded if not zone_blocked(xs[c[0]], ys[c[1]])}
    a_cells, b_edge = split_ab(usable, inner_ratio)

    # held-out B에는 A 셀 **사이** 지점도 넣는다 (docs §6). 학습 분포의 바깥(외삽)과
    # 안쪽 빈틈(내삽)을 같은 평가 축에서 구분하려는 것이다.
    data = mujoco.MjData(model)
    idx = arm_index(model)
    b_interp = []
    for i, j in sorted(a_cells):
        if not all((i + di, j + dj) in a_cells for di, dj in ((1, 0), (0, 1), (1, 1))):
            continue
        x = float(xs[i] + pitch / 2)
        y = float(ys[j] + pitch / 2)
        if zone_blocked(x, y):
            continue
        res = best_ik(model, data, idx, np.array([x, y, grasp_z]))
        if res.ok and res.margin >= margin_min:
            b_interp.append((x, y))

    to_xy = lambda cells: sorted((round(float(xs[i]), 4), round(float(ys[j]), 4)) for i, j in cells)
    return {
        "xs": xs,
        "ys": ys,
        "solved": result["solved"],
        "margins": {c: result["candidates"][c].margin for c in usable},
        "counts": {
            "grid": len(xs) * len(ys),
            "ik_solved": len(result["solved"]),
            "candidate": len(candidates),
            "eroded": len(eroded),
            "zone_excluded": len(eroded) - len(usable),
            "A": len(a_cells),
            "B_edge": len(b_edge),
            "B_interp": len(b_interp),
        },
        "A": to_xy(a_cells),
        "B_edge": to_xy(b_edge),
        "B_interp": [(round(x, 4), round(y, 4)) for x, y in b_interp],
    }


def _provenance(model) -> dict:
    import hashlib
    import subprocess

    import mujoco

    from trainyard.sim.scene import MODEL_XML, menagerie_dir

    try:
        commit = subprocess.run(
            ["git", "-C", str(menagerie_dir()), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 - 메뉴저리가 git 체크아웃이 아닐 수도 있다
        commit = "unknown"
    return {
        "ticket": "TY-13",
        "mujoco": mujoco.__version__,
        "menagerie_commit": commit,
        "scene_sha256": hashlib.sha256(MODEL_XML.read_bytes()).hexdigest()[:16],
    }


def _yaml(grid: dict, prov: dict) -> str:
    def points(items, indent="    "):
        return "\n".join(f"{indent}- [{x:.4f}, {y:.4f}]" for x, y in items)

    c = grid["counts"]
    return f"""# pick-and-place 태스크 파라미터 — **생성물이다. 손으로 고치지 않는다.**
#
#   PYTHONPATH=platform/src .venv/bin/python -m trainyard.sim.reach --out config/task/pick_place.yaml
#
# 근거는 docs/task-pick-place.md. 여기 있는 수치의 성격은 두 가지다.
#   - 확정 수치(§2 · §3): 물체 · 목표 존 크기 · 성공 판정 — 문서에서 그대로 옮겨온다.
#   - 측정 수치(§6): 스폰 격자 — SO-101 MJCF에 top-down IK를 풀어 얻은 결과다 (TY-13).
# 이 파일을 읽는 곳: 씬 리셋(TY-17) · 평가 조건표(TY-44) · 성공 판정(TY-106) · RL 보상(TY-111).
schema_version: 1

# 베이스 하단 중심이 원점, +x 정면 · +y 왼쪽 · z 위. 테이블 상판 z = 0. 단위 m · rad.
frame: base

table:
  center: [{TABLE_CENTER[0]:.4f}, {TABLE_CENTER[1]:.4f}]
  size: [{TABLE_SIZE[0]:.4f}, {TABLE_SIZE[1]:.4f}]   # x(깊이) × y(폭)
  top_z: 0.0

object:
  type: cube
  size: 0.025      # 한 변
  mass: 0.02
  spawn_z: {GRASP_Z:.4f}   # 중심 높이 = 한 변의 절반

# v0~v4 내내 고정 (docs §2). 스폰 격자는 이 사각형 + 물체 반폭만큼을 비워둔다.
target_zone:
  center: [{ZONE_CENTER[0]:.4f}, {ZONE_CENTER[1]:.4f}]
  size: [{ZONE_SIZE[0]:.4f}, {ZONE_SIZE[1]:.4f}]

# 성공 판정 (docs §3 — 확정). placed AND settled AND intact.
success:
  placed_z_max: 0.02
  settle_speed_max: 0.02
  settle_hold_s: 0.5
  timeout_s: 20.0
  lift_height: 0.05        # grasp_miss 판정 기준 (docs §4)

# 평가 조건표 축 (docs §6). 큐브는 90° 주기라 yaw 셋으로 전 범위를 덮는다.
evaluation:
  yaw_deg: [0, 30, 60]
  seeds: 5
  position_jitter: 0.003   # ±3mm
  yaw_jitter_deg: 3.0

spawn_grid:
  pitch: {GRID_PITCH:.3f}
  grasp_z: {GRASP_Z:.4f}
  joint_margin_min: {MARGIN_MIN:.2f}   # 관절 한계까지 남은 여유 / 가동범위
  inner_ratio_max: {INNER_RATIO:.2f}   # A가 이 비율을 넘으면 층을 한 겹 더 벗긴다
  counts:
    grid: {c["grid"]}
    ik_solved: {c["ik_solved"]}
    candidate: {c["candidate"]}       # IK 해 + 관절 여유 {int(MARGIN_MIN * 100)}% 이상
    eroded: {c["eroded"]}          # 경계에서 한 칸 안쪽
    zone_excluded: {c["zone_excluded"]}
    A: {c["A"]}
    B_edge: {c["B_edge"]}
    B_interp: {c["B_interp"]}
    A_ratio: {c["A"] / max(c["A"] + c["B_edge"], 1):.2f}
  # 학습 분포 A — 시연 수집(docs §9)과 학습은 여기서만 샘플한다.
  A:
{points(grid["A"])}
  # held-out B (1) 바깥 테두리 — 학습 분포 밖으로의 외삽.
  B_edge:
{points(grid["B_edge"])}
  # held-out B (2) A 셀 사이 지점 (반 칸 = {int(GRID_PITCH * 500)}mm 어긋난 곳) — 분포 안쪽의 내삽.
  B_interp:
{points(grid["B_interp"])}

provenance:
  ticket: {prov["ticket"]}
  mujoco: {prov["mujoco"]}
  menagerie_commit: {prov["menagerie_commit"]}
  scene_sha256: {prov["scene_sha256"]}
  method: >-
    테이블 작업 영역을 {int(GRID_PITCH * 1000)}mm 격자로 나눠 각 셀 중심에 top-down 파지 자세로 IK를 풀고
    (감쇠 최소자승, 위치 오차 < {POS_TOL * 1000:.1f}mm), 관절 한계 여유 {int(MARGIN_MIN * 100)}% 이상인 셀만 남긴 뒤
    경계에서 한 칸 안으로 줄이고 목표 존과 겹치는 셀을 뺐다. 남은 영역에서 가장자리 층을
    B로 떼어내고 안쪽을 A로 삼았다 — A가 {int(INNER_RATIO * 100)}%를 넘으면 층을 한 겹 더 벗긴다.
"""


def _main(argv=None) -> int:
    import argparse
    import time
    from pathlib import Path

    from trainyard.sim.scene import load_model

    parser = argparse.ArgumentParser(description="도달성 스윕 → config/task/pick_place.yaml")
    parser.add_argument("--out", type=Path, help="YAML 출력 경로 (없으면 표준출력)")
    parser.add_argument("--map", action="store_true", help="격자를 ASCII로 그린다")
    args = parser.parse_args(argv)

    model = load_model()
    t0 = time.perf_counter()
    grid = build_grid(model)
    elapsed = time.perf_counter() - t0
    text = _yaml(grid, _provenance(model))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"{args.out}  ({elapsed:.1f}s, {grid['counts']})")
    else:
        print(text)

    if args.map:
        a = set(grid["A"])
        b = set(grid["B_edge"])
        for x in reversed(grid["xs"]):
            row = "".join(
                "A" if (round(float(x), 4), round(float(y), 4)) in a
                else "B" if (round(float(x), 4), round(float(y), 4)) in b
                else "."
                for y in grid["ys"]
            )
            print(f"{x:5.2f} {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
