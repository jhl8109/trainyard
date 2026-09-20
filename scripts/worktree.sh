#!/usr/bin/env bash
# 티켓 하나당 워크트리 하나. 세션도 하나.
#
#   scripts/worktree.sh add TY-14 sim-bridge-node        # main에서 딴다
#   scripts/worktree.sh add TY-15 camera --on TY-14      # [예외] 머지 안 된 TY-14 위에 쌓기
#   scripts/worktree.sh rm TY-14                         # 워크트리 정리 (브랜치는 남긴다)
#   scripts/worktree.sh prune [-n|-y]                    # 머지된 워크트리 정리 (-y: 빈 것까지)
#   scripts/worktree.sh ls
set -euo pipefail

REPO="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --path-format=absolute --git-common-dir)"
REPO="${REPO%/.git}"
ROOT="${TRAINYARD_WORKTREES:-$HOME/orca/workspaces/trainyard}"
VENV="$REPO/.venv"
# Linear가 주는 브랜치 이름의 접두어. 다른 걸 쓰려면 TY_BRANCH_PREFIX로 덮는다.
PREFIX="${TY_BRANCH_PREFIX:-jhl81094}"

usage() { sed -n '2,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 1; }

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

# 끝난 워크트리를 걷어낸다.
# squash merge는 브랜치 커밋이 main의 조상이 되지 않으므로 --merged로는 못 찾는다.
# "GitHub에서 PR이 머지됐다"가 유일하게 확실한 신호다 — 이것만 자동으로 지운다.
# 커밋 0개인 워크트리는 30초 전에 시작한 세션일 수도 있어서 경고만 하고, --yes 일 때만 지운다.
cmd_prune() {
  local dry=0 yes=0
  while [ $# -gt 0 ]; do
    case "$1" in
      -n|--dry-run) dry=1 ;;
      -y|--yes)     yes=1 ;;   # 커밋 0개 유령까지 지운다
      *) usage ;;
    esac
    shift
  done
  git -C "$REPO" fetch --quiet origin main

  local merged
  merged="$( (cd "$REPO" && gh pr list --state merged --limit 100 --json headRefName -q '.[].headRefName') 2>/dev/null || true)"

  local here; here="$(pwd -P)"
  local list; list="$(git -C "$REPO" worktree list --porcelain \
    | awk '/^worktree /{p=$2} /^branch /{sub("refs/heads/","",$2); print p"\t"$2}')"

  while IFS=$'\t' read -r path branch; do
    [ -n "$path" ] || continue
    [ "$path" = "$REPO" ] && continue                      # 메인 체크아웃은 건드리지 않는다
    if [ "$path" = "$here" ]; then echo "유지   $branch  (지금 이 워크트리)"; continue; fi
    if [ -n "$(git -C "$path" status --porcelain 2>/dev/null)" ]; then
      echo "유지   $branch  (커밋 안 된 변경이 있다)"; continue
    fi

    local ahead reason
    ahead="$(git -C "$REPO" rev-list --count "origin/main..$branch" 2>/dev/null || echo 0)"
    if printf '%s\n' "$merged" | grep -Fxq "$branch"; then
      reason="PR 머지됨"
    elif [ "$ahead" = "0" ] && [ "$yes" = "1" ]; then
      reason="커밋 0개 — 버려진 세션"
    elif [ "$ahead" = "0" ]; then
      echo "확인   $branch  (커밋 0개 — 진행 중인 세션이 아니면 --yes 로 지운다)"; continue
    else
      echo "유지   $branch  (미머지 · 커밋 ${ahead}개)"; continue
    fi

    if [ "$dry" = "1" ]; then echo "정리예정 $branch  ($reason)"; continue; fi
    git -C "$REPO" worktree remove "$path" && git -C "$REPO" branch -D "$branch" >/dev/null
    echo "정리   $branch  ($reason)"
  done <<< "$list"
}

cmd_ls() { git -C "$REPO" worktree list; }

case "${1:-}" in
  add) shift; cmd_add "$@" ;;
  rm)  shift; cmd_rm "$@" ;;
  prune) shift; cmd_prune "$@" ;;
  ls)  cmd_ls ;;
  *)   usage ;;
esac
