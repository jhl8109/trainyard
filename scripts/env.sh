# TrainYard 개발 셸. 실행하지 말고 source 한다.
#
#   source scripts/env.sh
#
# 한 번에 붙이는 것:
#   1. ROS 2 Jazzy underlay
#   2. ros2_ws/install 오버레이 (빌드되어 있으면)
#   3. venv 패키지(torch · mujoco · lerobot)를 PYTHONPATH로 ROS 파이썬에 연결
#   4. colcon 기본값 파일(ros2_ws/colcon-defaults.yaml)
#
# set -u 금지: /opt/ros/jazzy/setup.bash 가 unbound variable을 건드려 즉시 죽는다.
# set -e 도 금지: 사용자 셸에 그대로 들어가므로 한 번 실패하면 셸이 닫힌다.

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  echo "실행이 아니라 source 해야 한다:  source scripts/env.sh" >&2
  exit 1
fi

TY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TY_ROS_SETUP="${TY_ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
TY_VENV="$TY_ROOT/.venv"                       # 워크트리에서는 레포 루트 venv로 가는 심볼릭 링크
ty__state=()

# 1. underlay — 이미 source 되어 있으면 다시 하지 않는다 (경로가 중복으로 쌓인다)
if [ -n "$ROS_DISTRO" ]; then
  ty__state+=("ROS 2 $ROS_DISTRO (이미 source됨)")
elif [ -f "$TY_ROS_SETUP" ]; then
  # shellcheck disable=SC1090
  source "$TY_ROS_SETUP" && ty__state+=("ROS 2 $ROS_DISTRO")
else
  ty__state+=("ROS 2 없음 — $TY_ROS_SETUP 를 찾지 못했다 (docs/SETUP.md)")
fi

# 2. 오버레이 — 빌드 산출물이 있을 때만. local_setup이 아니라 setup을 쓴다(의존 underlay까지 복원).
if [ -n "$TY_ENV_NO_OVERLAY" ]; then
  ty__state+=("오버레이 건너뜀 (TY_ENV_NO_OVERLAY)")
elif [ -f "$TY_ROOT/ros2_ws/install/setup.bash" ]; then
  # shellcheck disable=SC1091
  source "$TY_ROOT/ros2_ws/install/setup.bash" && ty__state+=("오버레이 ros2_ws/install")
else
  ty__state+=("오버레이 없음 — scripts/build.sh 로 빌드한다")
fi

# 3. venv → ROS 파이썬 연결.
#
#    .venv/bin 을 PATH 앞에 두지 않는다. requirements.txt가 고정한 pip cmake(4.x)가
#    apt cmake(3.28)를 가리는데, ROS 2 패키지의 cmake_minimum_required(3.5 미만)를
#    CMake 4가 거부해서 colcon 빌드가 깨진다. 파이썬만 PYTHONPATH로 연결하고
#    인터프리터는 $TY_PYTHON 으로 명시해서 쓴다.
#
#    sys.path 순서는 PYTHONPATH(ROS → venv) → 표준 라이브러리 → /usr/lib/python3/dist-packages 다.
#    그래서 충돌 시 ROS 패키지가 이기고, venv가 apt 패키지를 이긴다(numpy 2.2 > apt numpy 1.26).
if [ -x "$TY_VENV/bin/python" ]; then
  export TY_PYTHON="$TY_VENV/bin/python"
  ty__site="$("$TY_PYTHON" -c 'import sysconfig; print(sysconfig.get_path("purelib"))' 2>/dev/null)"
  case ":${PYTHONPATH}:" in
    *":$ty__site:"*) ;;
    *) export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$ty__site" ;;
  esac
  ty__state+=("venv $(basename "$(dirname "$ty__site")")/site-packages → PYTHONPATH, \$TY_PYTHON")
  unset ty__site
else
  ty__state+=("venv 없음 — uv venv --system-site-packages --python 3.12 (docs/SETUP.md)")
fi

# 4. colcon 기본값 — 래퍼로 돌리든 colcon을 직접 치든 같은 옵션이 걸린다
export COLCON_DEFAULTS_FILE="$TY_ROOT/ros2_ws/colcon-defaults.yaml"

# MuJoCo 헤드리스 렌더. 이미 정해둔 값이 있으면 건드리지 않는다.
export MUJOCO_GL="${MUJOCO_GL:-egl}"

if [ -z "$TY_ENV_QUIET" ]; then
  printf 'TrainYard %s\n' "$TY_ROOT"
  printf '  · %s\n' "${ty__state[@]}"
fi
unset ty__state
