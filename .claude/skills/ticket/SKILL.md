---
name: ticket
description: Work a TrainYard Linear ticket end to end — worktree, branch, implementation, verification, PR, Linear update. Use when the user types /ticket TY-14 (one ticket in this session) or /ticket next (drive the queue, one fresh agent per ticket). Also use when asked to pick up the next ticket, continue the backlog, or work through the queue.
---

# 티켓 실행

인자로 받은 형태에 따라 두 모드다.

- `TY-14` 같은 티켓 번호 → **단일 모드**: 이 세션에서 그 티켓 하나를 끝낸다
- `next` 또는 인자 없음 → **큐 모드**: 드라이버가 되어 티켓마다 새 에이전트를 띄운다

두 모드 모두 `CLAUDE.md`의 규약(자율 범위, 세션 종료 시 남길 것)을 그대로 따른다.

## 단일 모드 — `/ticket TY-14`

1. **읽기**
   ```bash
   python3 scripts/ty.py show TY-14
   ```
   부모 epic의 완료 조건과 코멘트를 함께 본다(`ty.py show <부모>`). 숫자가 필요하면 `docs/task-pick-place.md`를 읽는다.

2. **중단 조건 확인** — `type/spike` 또는 `needs/decision` 라벨이 붙어 있으면 **구현하지 않는다.** 선택지와 근거를 정리해 사용자에게 제시하고 끝낸다. 설계 숫자를 바꿔야 하는 티켓도 같다.

3. **워크트리** — base는 **항상 main**이다.
   ```bash
   scripts/worktree.sh add TY-14 sim-bridge-node
   ```
   선행 티켓을 신경 쓸 필요가 없다. `ty.py next`가 epic마다 아직 안 끝난 가장 낮은 번호 하나만 내보내므로, 큐에 나온 티켓은 이미 선행 티켓이 `Done`이라는 뜻이다. 브랜치를 쌓지 않으니 리베이스도 없다.

   `--on`은 예외 탈출구다. 큐를 건너뛰고 사람이 직접 지시했고 선행 PR이 아직 열려 있을 때만 쓴다. 그 경우 PR 본문에 `#N 머지 후 리베이스 필요`를 적고, 깊이는 1을 넘기지 않는다.

   생성된 워크트리로 이동해서 작업한다. `source /opt/ros/jazzy/setup.bash`를 먼저 한다.

4. **상태 변경** — `python3 scripts/ty.py state TY-14 "In Progress"`

5. **구현** — 티켓의 완료 조건을 만족시키는 최소 변경. 티켓 범위를 넘는 것을 발견하면 구현하지 말고 `ty.py sub`로 하위 이슈를 만들어 남긴다.

6. **검증** — 티켓 성격에 맞게 실행하고 **숫자를 남긴다.**
   - 코드: `pytest`, `colcon build --symlink-install`, 관련 노드 실행
   - 환경·의존성 변경: `bash scripts/verify_env.sh`
   - 주기·지연이 관련되면 실측(예: 루프 지터 p99, 퍼블리시 Hz)
   측정값이 필요한 티켓인데 측정하지 않았다면 완료가 아니다.

7. **커밋 · PR**
   ```bash
   git add <파일들>            # git add -A 는 쓰지 않는다 (다른 세션 작업이 섞인다)
   git commit                  # Conventional Commits + 왜 이 방식인지
   git push -u origin HEAD
   gh pr create --base <base> --title "..." --body "..."   # 템플릿 채우기, Fixes TY-14
   ```

8. **Linear 마감**
   ```bash
   python3 scripts/ty.py comment TY-14 "결정 · 수치 · 다음 티켓이 알아야 할 것 + PR 링크"
   python3 scripts/ty.py state TY-14 "In Review"
   ```
   다른 티켓의 전제를 바꿨다면 그 티켓에도 코멘트를 남긴다. 워크트리는 **지우지 않는다** — PR이 머지된 뒤 `worktree.sh prune`이 걷어간다.

9. **3줄 요약** — 무엇을 했나 / 수치 / 사용자에게 필요한 결정(머지 포함).

## 큐 모드 — `/ticket next`

드라이버는 **구현하지 않는다.** 컨텍스트를 작게 유지하고 티켓마다 에이전트를 띄운다.

1. **청소하고 큐를 읽는다.**
   ```bash
   bash scripts/worktree.sh prune          # 머지된 워크트리를 걷어낸다
   python3 scripts/ty.py next -n 10
   gh pr list --state open --json number,title,headRefName   # 사용자가 머지할 것들
   ```
   `next`의 "진행 중" 항목은 **사람이 머지해야 열리는 것들**이다. 큐가 비어 있으면 더 할 일이 없는 게 아니라 머지 대기다 — 그 목록을 사용자에게 보여주고 멈춘다.

2. 큐에 나온 티켓들에 대해 `Agent`를 띄운다(`subagent_type: "general-purpose"`). 큐의 티켓은 서로 다른 epic에 속하고 전부 main에서 갈라지므로 **동시에 띄워도 된다.** 프롬프트에 넣을 것:
   - 티켓 번호와 "`.claude/skills/ticket/SKILL.md`의 단일 모드 1~8단계를 따르라"
   - 저장소 경로와 `CLAUDE.md`를 먼저 읽으라는 지시
   - 돌려줄 보고 형식: `티켓 / PR 링크 / 수치 / 막힌 점(있으면)` 4줄

3. 에이전트 보고를 받으면 큐를 다시 읽는다. **다음 중 하나면 멈추고 사용자에게 보고한다.**
   - 큐가 비었다 — 머지 대기다. 머지할 PR 목록을 보여준다
   - 큐에 `type/spike` · `needs/decision`만 남았다
   - 에이전트가 막혔다고 보고했다 (그 티켓에 `needs/decision` 라벨이 붙어 있는지 확인)
   - 에이전트가 실패했거나 CI가 깨졌다
   - 사용자가 지정한 티켓 수를 소화했다 (기본 3개)

4. 마지막에 표로 보고한다: 티켓 / PR / 수치 / 상태. 그리고 사용자가 할 일(머지할 PR 목록, 필요한 결정)을 적는다.

### 루프를 누가 돌리나

드라이버는 사용자가 띄운 세션이다. 데몬은 없다. 머지는 사람이 하므로 **큐는 머지에서 마른다** — 이건 설계된 동작이고, 브랜치를 쌓아서 가리지 않는다.

머지는 어디서 하든 상관없다(GitHub 웹·모바일). 드라이버는 Linear 상태만 보고, PR이 머지되면 티켓이 `Done`으로 자동 전이되면서 같은 epic의 다음 티켓이 큐에 나타난다. 머지 후 재기동은 사용자가 `/ticket next`를 다시 치거나, `/loop 20m /ticket next`로 맡긴다.

## 하지 않는 것

- PR 머지 (사람이 한다)
- `main` 직접 push, force push
- 설계 숫자 변경 — 태스크 정의 · 평가 조건표 · 인터페이스 계약은 spike에서 사람이 정한다
- 하드웨어 주문, 레포 설정 변경, 공개 범위 변경
- `git add -A` / `git commit -a` (다른 워크트리·세션 작업이 섞인다)
