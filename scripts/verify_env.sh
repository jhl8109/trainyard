#!/usr/bin/env bash
# 개발 환경이 온전한지 검증한다. 셋업 직후 · 재부팅 후 · CI에서 실행.
# 실패한 항목만 비정상 종료 코드로 알린다.
# set -u 는 쓰지 않는다: /opt/ros/jazzy/setup.bash 가 unbound variable
# (AMENT_TRACE_SETUP_FILES 등)을 참조해서 즉시 죽는다.
set -o pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO/.venv/bin/python"
MODEL="${MENAGERIE:-$HOME/orca/mujoco_menagerie}/robotstudio_so101/scene.xml"
ROS_SETUP=/opt/ros/jazzy/setup.bash
fail=0

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=1; }
head_() { printf '\n\033[1m%s\033[0m\n' "$1"; }

# ros2 · rclpy 확인보다 먼저 source 해야 한다.
if [ -f "$ROS_SETUP" ]; then
  # shellcheck disable=SC1090
  source "$ROS_SETUP"
fi

head_ "도구"
for c in ros2 colcon rosdep cmake g++ ffmpeg; do
  if command -v "$c" >/dev/null; then ok "$c"; else bad "$c 없음"; fi
done
[ -x "$PY" ] && ok "venv ($PY)" || bad "venv 없음 — uv venv --system-site-packages 필요"

head_ "GPU 드라이버"
if command -v nvidia-smi >/dev/null && nvidia-smi >/dev/null 2>&1; then
  ok "$(nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader)"
else
  bad "nvidia-smi 실패 — 드라이버 미설치거나 재부팅 필요"
fi
lsmod | grep -q '^nouveau' && bad "nouveau가 아직 로드됨 (재부팅 필요)" || ok "nouveau 언로드됨"

head_ "ROS 2"
if [ -f "$ROS_SETUP" ]; then
  ok "jazzy sourced (ROS_DISTRO=$ROS_DISTRO)"
  pkgs=$(ros2 pkg list 2>/dev/null)
  for p in rosbag2_storage_mcap ros2_control joy cv_bridge kdl_parser xacro robot_state_publisher; do
    grep -qx "$p" <<<"$pkgs" && ok "$p" || bad "$p 없음"
  done
else
  bad "$ROS_SETUP 없음"
fi

head_ "Python 스택"
[ -x "$PY" ] && MUJOCO_GL="${MUJOCO_GL:-egl}" MODEL="$MODEL" "$PY" - <<'PY'
import os, sys
bad = []
def chk(label, fn):
    try:
        print(f"  \033[32m✓\033[0m {label}: {fn()}")
    except Exception as e:
        print(f"  \033[31m✗\033[0m {label}: {type(e).__name__}: {e}")
        bad.append(label)

import importlib
for mod in ("rclpy", "torch", "mujoco", "lerobot", "cv2", "numpy", "scipy"):
    chk(mod, lambda m=mod: importlib.import_module(m).__version__
        if hasattr(importlib.import_module(m), "__version__") else "ok")

def cuda():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("torch.cuda.is_available() == False")
    p = torch.cuda.get_device_properties(0)
    x = torch.randn(2048, 2048, device="cuda"); (x @ x).sum().item()
    return f"{torch.cuda.get_device_name(0)} sm_{p.major}{p.minor} {p.total_memory/1024**3:.1f}GB, matmul OK"
chk("CUDA 연산", cuda)

def render():
    import mujoco
    m = mujoco.MjModel.from_xml_path(os.environ["MODEL"])
    d = mujoco.MjData(m); mujoco.mj_forward(m, d)
    r = mujoco.Renderer(m, 240, 320)
    try:
        r.update_scene(d)
        img = r.render()
        assert img.any(), "렌더 결과가 비어있음"
        for _ in range(500):
            mujoco.mj_step(m, d)
        return f"{img.shape} 렌더 + 500스텝, 액추에이터 {m.nu}개"
    finally:
        r.close()   # 명시적 close 없이 GC에 맡기면 종료 시 EGLError 트레이스백이 난다
chk("MuJoCo GPU 렌더 + SO-101", render)

sys.exit(1 if bad else 0)
PY
[ $? -ne 0 ] && fail=1

head_ "의존성 정합성"
if command -v uv >/dev/null; then
  out=$(cd "$REPO" && uv pip check 2>&1)
  grep -q 'All installed packages are compatible' <<<"$out" \
    && ok "uv pip check 통과" || { bad "의존성 충돌"; sed 's/^/      /' <<<"$out" | head -5; }
else
  bad "uv 없음"
fi

if [ $fail -eq 0 ]; then
  printf '\n\033[32m환경 검증 통과\033[0m\n'
else
  printf '\n\033[31m실패한 항목이 있다 — docs/SETUP.md 참고\033[0m\n'
fi
exit $fail
