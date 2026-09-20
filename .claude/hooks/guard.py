#!/usr/bin/env python3
"""PreToolUse 훅 — CLAUDE.md 규약 중 '되돌리기 어려운 것'만 실행 가능한 규칙으로 만든다.

산문으로 적은 금지는 settings.json의 허용 목록과 모순될 수 있다(`git add -A` 금지인데
`Bash(git add:*)` 허용). 여러 세션이 동시에 도는 레포에서 add -A 한 번이면 남의 작업이
섞여 들어가므로, 부탁이 아니라 차단으로 둔다.

차단 결과는 exit 2 + stderr로 돌려준다(Claude가 읽고 다른 방법을 찾는다).
"""
from __future__ import annotations

import json
import re
import sys

RULES: list[tuple[str, str]] = [
    (r"\bgit\s+add\s+(?:-[A-Za-z]*A|--all)\b|\bgit\s+add\s+\.(?:\s|$)",
     "`git add -A` / `git add .` 금지 — 워크트리가 여러 개라 다른 세션이 만든 파일이 섞인다. "
     "바꾼 파일을 명시해서 add 한다."),
    (r"\bgit\s+commit\b[^;&|]*\s-(?!-)[A-Za-z]*a[A-Za-z]*\b|\bgit\s+commit\b[^;&|]*\s--all\b",
     "`git commit -a` 금지 — 같은 이유다. `git add <파일>` 후에 커밋한다."),
    (r"\bgit\s+push\b[^;&|]*--force(?!-with-lease)\b",
     "`git push --force` 금지 — 필요하면 `--force-with-lease`를 쓴다."),
    (r"\bgit\s+push\b[^;&|]*\borigin\s+main\b|\bgit\s+push\b[^;&|]*\bHEAD:main\b",
     "`main` 직접 push 금지 — PR을 올린다. (서버 ruleset도 막지만 여기서 먼저 잡는다)"),
]

# 커밋 메시지나 PR 본문이 규칙 자체를 인용할 수 있다 — 이 훅을 설명하는 커밋이 그랬다.
# 그래서 명령이 아닌 구간(따옴표 문자열 · 히어독 본문)은 지우고 본다.
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?^\s*\2\s*$", re.DOTALL | re.MULTILINE)


def strip_noncommand(command: str) -> str:
    """실행되지 않는 텍스트를 걷어낸다. 히어독을 먼저 지워야 그 안의 따옴표에 안 휘말린다."""
    return QUOTED.sub(" ", HEREDOC.sub(" ", command))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = strip_noncommand(payload.get("tool_input", {}).get("command", ""))
    for pattern, reason in RULES:
        if re.search(pattern, command):
            print(f"TrainYard 규약 위반 — {reason}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
