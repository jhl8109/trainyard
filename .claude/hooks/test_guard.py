"""guard.py 회귀 테스트.

  python3 .claude/hooks/test_guard.py

오탐이 제일 위험하다 — 이 훅을 설명하는 커밋 메시지가 훅에 막히면서 발견됐다.
그래서 '규칙을 인용하는 커밋 본문'이 통과하는지를 함께 고정한다.
"""
import json
import subprocess
import sys
from pathlib import Path

HOOK = str(Path(__file__).with_name("guard.py"))

CASES = [
    # (기대, 설명, 명령)
    ("차단", "add -A", "git add -A"),
    ("차단", "add .", "git add ."),
    ("차단", "add --all, 복합 명령", "cd x && git add --all"),
    ("차단", "commit -am", 'git commit -am "fix"'),
    ("차단", "commit -a", "git commit -a"),
    ("차단", "push --force", "git push --force origin HEAD"),
    ("차단", "main 직접 push", "git push origin main"),
    ("차단", "HEAD:main push", "git push HEAD:main"),
    ("통과", "파일 명시 add", "git add CLAUDE.md scripts/ty.py"),
    ("통과", "amend", "git commit --amend --no-edit"),
    ("통과", "정상 push", "git push -u origin HEAD"),
    ("통과", "force-with-lease", "git push --force-with-lease"),
    ("통과", "메시지가 규칙을 인용", 'git commit -m "feat: add -A 금지 규칙"'),
    (
        "통과",
        "히어독 커밋 본문이 규칙을 인용",
        "git commit -q -F - <<'EOF'\n"
        "feat(devloop): 규약을 훅으로 강제한다\n\n"
        "git add -A 는 다른 세션 파일을 섞는다.\n"
        "git push --force 도 막는다. git commit -a 도 마찬가지다.\n"
        "EOF",
    ),
    (
        "통과",
        "PR 본문 히어독",
        "gh pr create --body \"$(cat <<'EOF'\n- git add -A 차단\n- git push origin main 차단\nEOF\n)\"",
    ),
    ("통과", "Bash 이외 도구", None),
]


def run(cmd: str, tool: str = "Bash") -> int:
    payload = {"tool_name": tool, "tool_input": {"command": cmd} if cmd else {}}
    return subprocess.run(
        [sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True
    ).returncode


bad = 0
for want, label, cmd in CASES:
    rc = run(cmd or "", tool="Bash" if cmd else "Read")
    got = "차단" if rc == 2 else "통과"
    ok = got == want
    bad += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} 기대={want} 실제={got}  {label}")

print(f"\n{len(CASES) - bad}/{len(CASES)} 통과")
sys.exit(1 if bad else 0)
