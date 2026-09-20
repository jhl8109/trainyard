#!/usr/bin/env bash
# ROS 2 워크스페이스 빌드 래퍼. 어느 디렉터리에서 실행해도 ros2_ws 를 빌드한다.
#
#   scripts/build.sh                      전체 빌드
#   scripts/build.sh ty_msgs ty_sim       그 패키지와 의존 패키지까지 (--packages-up-to)
#   scripts/build.sh --test [패키지...]   빌드 후 colcon test + 실패 요약
#   scripts/build.sh --clean [패키지...]  build/ install/ log/ 를 지우고 빌드
#   scripts/build.sh -- --cmake-clean-cache    '--' 뒤는 colcon 에 그대로 넘긴다
#
# 빌드 옵션은 ros2_ws/colcon-defaults.yaml 에 둔다 — colcon 을 직접 쳐도 같은 옵션이 걸리게.
# set -u 는 쓰지 않는다: ROS setup.bash 가 unbound variable 을 건드린다.
set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS="$ROOT/ros2_ws"

usage() { sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 1; }

clean=0 run_test=0 pkgs=() passthru=()
while [ $# -gt 0 ]; do
  case "$1" in
    --clean) clean=1 ;;
    --test)  run_test=1 ;;
    -h|--help) usage ;;
    --) shift; passthru=("$@"); break ;;
    -*) echo "모르는 옵션: $1" >&2; usage ;;
    *) pkgs+=("$1") ;;
  esac
  shift
done

# 오버레이는 붙이지 않는다. 자기 자신의 install/ 을 source 한 채로 빌드하면
# colcon 이 경고만 하고 넘어가면서 옛 산출물을 참조하는 빌드가 조용히 섞인다.
export TY_ENV_QUIET=1 TY_ENV_NO_OVERLAY=1
# shellcheck disable=SC1091
source "$ROOT/scripts/env.sh"
[ -n "$ROS_DISTRO" ] || { echo "ROS 2 를 찾지 못했다 — docs/SETUP.md 를 본다" >&2; exit 1; }

if [ "$clean" = "1" ]; then
  rm -rf "$WS/build" "$WS/install" "$WS/log"
  echo "정리   ros2_ws/{build,install,log}"
fi

# --packages-up-to: 이름만 고르면 의존 패키지(ty_msgs 등)가 빠져 링크가 깨진다
select_args=()
[ ${#pkgs[@]} -gt 0 ] && select_args=(--packages-up-to "${pkgs[@]}")

t0=$SECONDS
( cd "$WS" && colcon build "${select_args[@]}" "${passthru[@]}" )
# 패키지 수는 위 colcon 요약이 이미 말한다. 여기서는 벽시계 시간만 남긴다.
echo "빌드   $((SECONDS - t0))s"

if [ "$run_test" = "1" ]; then
  t0=$SECONDS
  # colcon test 는 테스트가 깨져도 0 으로 끝나는 경우가 있다. 합격 판정은 test-result 가 한다.
  ( cd "$WS" && colcon test "${select_args[@]}" ) || true
  echo "테스트 $((SECONDS - t0))s"
  ( cd "$WS" && colcon test-result --verbose )
fi

echo
echo "  source $ROOT/scripts/env.sh   # 빌드 결과를 셸에 붙인다"
