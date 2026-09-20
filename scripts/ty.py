#!/usr/bin/env python3
"""Linear(TY 팀) CLI. 세션마다 GraphQL을 다시 쓰지 않기 위한 얇은 래퍼.

API 키는 ~/.config/trainyard/linear.env 또는 환경변수 LINEAR_API_KEY.

  ty.py show TY-14                 티켓 본문 + 코멘트
  ty.py next [-n 5]                작업 가능한 티켓 큐 (릴리즈 → 번호 순)
  ty.py state TY-14 "In Review"    상태 변경
  ty.py comment TY-14 "본문"        코멘트 (본문 생략 시 stdin)
  ty.py label TY-14 needs/decision 라벨 추가
  ty.py sub TY-12 "제목"            하위 이슈 생성 (티켓이 커질 때 쪼갠다)
  ty.py epic TY-12                 epic + 하위 티켓 상태 일람
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

API = "https://api.linear.app/graphql"
ENV_FILE = Path.home() / ".config/trainyard/linear.env"
# 큐에서 제외: 사람 판단이 필요한 것들
BLOCKING_LABELS = {"type/spike", "needs/decision"}
# 상태는 이름이 아니라 Linear 상태 타입으로 판정한다 (팀이 이름을 바꿔도 안 깨진다)
DONE_TYPES = {"completed", "canceled", "duplicate"}
STARTED_TYPES = {"started"}        # In Progress · In Review = 누군가 잡고 있다
ACTIONABLE_TYPES = {"backlog", "unstarted"}


def api_key() -> str:
    if key := os.environ.get("LINEAR_API_KEY"):
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("LINEAR_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit(f"LINEAR_API_KEY 없음 — 환경변수 또는 {ENV_FILE}")


def gql(query: str, variables: dict | None = None) -> dict:
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": api_key(), "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        out = json.load(resp)
    if "errors" in out:
        sys.exit(json.dumps(out["errors"], ensure_ascii=False, indent=2))
    return out["data"]


def team_id() -> str:
    for t in gql("{ teams { nodes { id key } } }")["teams"]["nodes"]:
        if t["key"] == "TY":
            return t["id"]
    sys.exit("TY 팀을 찾을 수 없다")


ISSUE_FIELDS = """
  id identifier title priority url
  state { name type }
  project { name }
  parent { identifier title }
  labels { nodes { name } }
  children { nodes { identifier title state { name } } }
"""


def find_issue(ident: str) -> dict:
    num = int(ident.upper().removeprefix("TY-"))
    nodes = gql(
        "query($t:String!,$n:Float!){ team(id:$t){ issues(filter:{number:{eq:$n}}){ nodes { "
        + ISSUE_FIELDS
        + " description } } } }",
        {"t": team_id(), "n": num},
    )["team"]["issues"]["nodes"]
    if not nodes:
        sys.exit(f"{ident} 없음")
    return nodes[0]


def release_order(project_name: str | None) -> tuple[int, str]:
    """프로젝트 이름의 v숫자로 릴리즈 순서를 만든다. 프로젝트 없으면 맨 뒤."""
    if not project_name:
        return (99, "")
    m = re.match(r"v(\d+)", project_name)
    return (int(m.group(1)) if m else 98, project_name)


def cmd_show(args) -> None:
    issue = find_issue(args.ident)
    labels = ", ".join(n["name"] for n in issue["labels"]["nodes"]) or "-"
    print(f"{issue['identifier']}  {issue['title']}")
    print(f"  상태 {issue['state']['name']} · 프로젝트 {issue['project']['name'] if issue['project'] else '-'} · 라벨 {labels}")
    if issue["parent"]:
        print(f"  부모 {issue['parent']['identifier']} {issue['parent']['title']}")
    print(f"  {issue['url']}\n")
    print(issue["description"] or "(본문 없음)")
    kids = issue["children"]["nodes"]
    if kids:
        print("\n하위 티켓")
        for k in kids:
            print(f"  {k['identifier']:8} [{k['state']['name']:11}] {k['title']}")
    comments = gql(
        "query($id:String!){ issue(id:$id){ comments { nodes { createdAt body user { name } } } } }",
        {"id": issue["id"]},
    )["issue"]["comments"]["nodes"]
    if comments:
        print("\n코멘트")
        for c in comments:
            who = c["user"]["name"] if c["user"] else "-"
            print(f"  --- {c['createdAt'][:16]} {who}")
            for line in (c["body"] or "").splitlines():
                print(f"  {line}")


def issue_num(issue: dict) -> int:
    return int(issue["identifier"].split("-")[1])


def sort_key(issue: dict) -> tuple:
    return (release_order(issue["project"]["name"] if issue["project"] else None), issue_num(issue))


def cmd_next(args) -> None:
    """큐 = epic마다 '아직 안 끝난 가장 낮은 번호' 하나.

    Linear에 의존 관계가 입력돼 있지 않으므로 epic 하위 번호 순을 의존 순서로 쓴다.
    앞 티켓이 Done이 되기 전에는 다음 티켓이 큐에 나타나지 않는다 — 그래서
    브랜치를 쌓을 일이 없고 모든 워크트리가 main에서 갈라진다.
    """
    issues = gql(
        "query($t:String!){ team(id:$t){ issues(first:250){ nodes { " + ISSUE_FIELDS + " } } } }",
        {"t": team_id()},
    )["team"]["issues"]["nodes"]

    groups: dict[str, list] = {}
    for i in issues:
        if i["children"]["nodes"]:  # epic은 직접 작업하지 않는다
            continue
        # 부모 없는 티켓은 그 자체로 하나의 그룹이다
        groups.setdefault(i["parent"]["identifier"] if i["parent"] else i["identifier"], []).append(i)

    queue, waiting, blocked, hidden = [], [], [], []
    for members in groups.values():
        members.sort(key=issue_num)
        head = next((m for m in members if m["state"]["type"] not in DONE_TYPES), None)
        if head is None:
            continue  # epic 완료
        labels = {n["name"] for n in head["labels"]["nodes"]}
        if labels & BLOCKING_LABELS:
            blocked.append(head)
        elif head["state"]["type"] in STARTED_TYPES:
            waiting.append(head)
        elif head["state"]["type"] in ACTIONABLE_TYPES:
            queue.append(head)
        hidden += [
            m for m in members
            if m is not head
            and m["state"]["type"] not in DONE_TYPES
            and {n["name"] for n in m["labels"]["nodes"]} & BLOCKING_LABELS
        ]

    print("작업 가능 (epic당 1개 · 전부 main에서 딴다)")
    if not queue:
        print("  (없음 — 아래 '진행 중'을 머지하면 다음 티켓이 열린다)")
    for i in sorted(queue, key=sort_key)[: args.count]:
        proj = i["project"]["name"] if i["project"] else "-"
        print(f"  {i['identifier']:8} [{proj[:24]:26}] {i['title']}")

    if waiting:
        print("\n진행 중 — 이게 Done이 돼야 같은 epic의 다음 티켓이 열린다")
        for i in sorted(waiting, key=sort_key):
            parent = i["parent"]["identifier"] if i["parent"] else "-"
            print(f"  {i['identifier']:8} [{i['state']['name']:11}] {parent:7} {i['title']}")

    if blocked:
        print("\n사람 판단 필요 — epic을 막고 있다")
        for i in sorted(blocked, key=sort_key):
            names = ", ".join(sorted({n["name"] for n in i["labels"]["nodes"]} & BLOCKING_LABELS))
            print(f"  {i['identifier']:8} [{names:16}] {i['title']}")

    if hidden:
        print(f"\n(뒤쪽에 spike·needs/decision {len(hidden)}개 — 해당 epic 차례가 오면 나타난다)")


def cmd_state(args) -> None:
    issue = find_issue(args.ident)
    states = gql("query($t:String!){ team(id:$t){ states { nodes { id name } } } }",
                 {"t": team_id()})["team"]["states"]["nodes"]
    match = next((s for s in states if s["name"].lower() == args.state.lower()), None)
    if not match:
        sys.exit("상태 이름: " + ", ".join(s["name"] for s in states))
    gql("mutation($id:String!,$i:IssueUpdateInput!){ issueUpdate(id:$id,input:$i){ success } }",
        {"id": issue["id"], "i": {"stateId": match["id"]}})
    print(f"{issue['identifier']} → {match['name']}")


def cmd_comment(args) -> None:
    body = args.body if args.body is not None else sys.stdin.read()
    if not body.strip():
        sys.exit("빈 코멘트")
    issue = find_issue(args.ident)
    gql("mutation($i:CommentCreateInput!){ commentCreate(input:$i){ success } }",
        {"i": {"issueId": issue["id"], "body": body}})
    print(f"{issue['identifier']} 코멘트 추가")


def cmd_label(args) -> None:
    issue = find_issue(args.ident)
    labels = gql("query($t:String!){ team(id:$t){ labels { nodes { id name } } } }",
                 {"t": team_id()})["team"]["labels"]["nodes"]
    match = next((l for l in labels if l["name"] == args.label), None)
    if not match:
        sys.exit("라벨 이름: " + ", ".join(l["name"] for l in labels))
    current = [n["name"] for n in issue["labels"]["nodes"]]
    ids = [l["id"] for l in labels if l["name"] in set(current) | {args.label}]
    gql("mutation($id:String!,$i:IssueUpdateInput!){ issueUpdate(id:$id,input:$i){ success } }",
        {"id": issue["id"], "i": {"labelIds": ids}})
    print(f"{issue['identifier']} + {args.label}")


def cmd_sub(args) -> None:
    parent = find_issue(args.ident)
    detail = gql("query($id:String!){ issue(id:$id){ teamId project { id } labels { nodes { id } } } }",
                 {"id": parent["id"]})["issue"]
    inp = {"teamId": detail["teamId"], "parentId": parent["id"], "title": args.title,
           "labelIds": [n["id"] for n in detail["labels"]["nodes"]]}
    if detail["project"]:
        inp["projectId"] = detail["project"]["id"]
    if args.description:
        inp["description"] = args.description
    r = gql("mutation($i:IssueCreateInput!){ issueCreate(input:$i){ issue { identifier url } } }",
            {"i": inp})["issueCreate"]["issue"]
    print(f"{r['identifier']} 생성 (부모 {parent['identifier']}) {r['url']}")


def cmd_epic(args) -> None:
    epic = find_issue(args.ident)
    print(f"{epic['identifier']}  {epic['title']}  [{epic['state']['name']}]")
    for k in epic["children"]["nodes"]:
        print(f"  {k['identifier']:8} [{k['state']['name']:11}] {k['title']}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("show"); s.add_argument("ident"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("next"); s.add_argument("-n", "--count", type=int, default=5); s.set_defaults(fn=cmd_next)
    s = sub.add_parser("state"); s.add_argument("ident"); s.add_argument("state"); s.set_defaults(fn=cmd_state)
    s = sub.add_parser("comment"); s.add_argument("ident"); s.add_argument("body", nargs="?"); s.set_defaults(fn=cmd_comment)
    s = sub.add_parser("label"); s.add_argument("ident"); s.add_argument("label"); s.set_defaults(fn=cmd_label)
    s = sub.add_parser("sub"); s.add_argument("ident"); s.add_argument("title")
    s.add_argument("-d", "--description"); s.set_defaults(fn=cmd_sub)
    s = sub.add_parser("epic"); s.add_argument("ident"); s.set_defaults(fn=cmd_epic)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
