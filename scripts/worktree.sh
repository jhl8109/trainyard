#!/usr/bin/env bash
# 티켓 하나당 워크트리 하나. 세션도 하나.
#
#   scripts/worktree.sh add TY-14 sim-bridge-node        # main에서 딴다
#   scripts/worktree.sh add TY-15 camera --on TY-14      # 머지 안 된 TY-14 위에 쌓는다
#   scripts/worktree.sh rm TY-14                         # 워크트리 정리 (브랜치는 남긴다)
#   scripts/worktree.sh ls
set -euo pipefail

REPO="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --path-format=absolute --git-common-dir)"
REPO="${REPO%/.git}"
ROOT="${TRAINYARD_WORKTREES:-$HOME/orca/workspaces/trainyard}"
VENV="$REPO/.venv"
# Linear가 주는 브랜치 이름의 접두어. 다른 걸 쓰려면 TY_BRANCH_PREFIX로 덮는다.
PREFIX="${TY_BRANCH_PREFIX:-jhl81094}"

usage() { sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 1; }

lower() { printf '%s' "$1" | tr 'A-Z' 'a-z'; }

cmd_add() {
  local ticket="${1:-}" slug="${2:-}" base="main"
  shift 2 || usage
  while [ $# -gt 0 ]; do
    case "$1" in
      # 접두어가 세션마다 다를 수 있으므로 티켓 번호로 찾는다
      --on) base="$(git -C "$REPO" branch --list "*$(lower "$2")-*" --format='%(refname:short)' | head -1)"
            [ -n "$base" ] || { echo "'--on $2'에 해당하는 브랜치가 없다" >&2; exit 1; }; shift 2 ;;
      *) usage ;;
    esac
  done
  [ -n "$ticket" ] && [ -n "$slug" ] || usage

  local key branch path
  key="$(lower "$ticket")"
  branch="${PREFIX}/${key}-${slug}"
  path="$ROOT/${key}"

  # 다른 세션이 이미 같은 티켓을 잡고 있으면 멈춘다
  if git -C "$REPO" worktree list --porcelain | grep -q "branch refs/heads/.*${key}-"; then
    echo "이미 다른 워크트리가 ${ticket}을 잡고 있다:" >&2
    git -C "$REPO" worktree list | grep -i "${key}" >&2
    exit 1
  fi

  if [ -d "$path" ]; then echo "이미 있다: $path"; exit 0; fi
  git -C "$REPO" fetch --quiet origin main
  [ "$base" = "main" ] && git -C "$REPO" branch --force main origin/main >/dev/null 2>&1 || true

  mkdir -p "$ROOT"
  git -C "$REPO" worktree add "$path" -b "$branch" "$base"
  # .venv는 레포 루트 하나만 쓴다 (gitignore 대상, 워크트리마다 만들지 않는다)
  [ -d "$VENV" ] && ln -sfn "$VENV" "$path/.venv"

  echo
  echo "워크트리 $path"
  echo "브랜치  $branch  (base: $base)"
  [ "$base" != "main" ] && echo "주의    base가 main이 아니다 — PR 본문에 '$base 머지 후 리베이스 필요'를 적는다"
  echo
  echo "  cd $path && source /opt/ros/jazzy/setup.bash"
}

cmd_rm() {
  local key path
  key="$(lower "${1:?티켓 번호}")"
  path="$ROOT/${key}"
  git -C "$REPO" worktree remove "$path" "${2:-}"
  echo "정리됨: $path (브랜치는 남아 있다)"
}

cmd_ls() { git -C "$REPO" worktree list; }

case "${1:-}" in
  add) shift; cmd_add "$@" ;;
  rm)  shift; cmd_rm "$@" ;;
  ls)  cmd_ls ;;
  *)   usage ;;
esac
