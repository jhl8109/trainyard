"""문서 사이트 빌드 훅 두 가지.

1. 랜딩(index.md)을 루트 README.md에서 만든다. docs/ 로 복사해 두면 두 벌이
   되고 반드시 갈라진다.
2. 문서가 가리키는 **레포 파일**(scripts/verify_env.sh · requirements.txt 등)
   링크를 GitHub blob URL로 바꾼다. 마크다운 원본은 레포에서 읽을 때 맞아야
   하므로 상대 경로 그대로 두고, 사이트 쪽만 빌드 시점에 고친다.
"""

import re
from pathlib import Path

from mkdocs.structure.files import File

LINK = re.compile(r"\]\(([^)#?\s]+)([^)]*)\)")


def _repo_root(config) -> Path:
    return Path(config.docs_dir).parent


def _blob(config, path: Path) -> str:
    rel = path.relative_to(_repo_root(config))
    return f"{config.repo_url.rstrip('/')}/blob/main/{rel}"


def _rewrite(markdown: str, config, base: Path) -> str:
    """base 기준 상대 링크 중 docs/ 바깥의 레포 파일을 blob URL로 바꾼다."""
    docs_dir = Path(config.docs_dir).resolve()

    def sub(m: re.Match) -> str:
        target, rest = m.group(1), m.group(2)
        if re.match(r"^(https?:|mailto:|/)", target):
            return m.group(0)
        resolved = (base / target).resolve()
        if not resolved.exists() or resolved.is_relative_to(docs_dir):
            return m.group(0)
        if not resolved.is_relative_to(_repo_root(config).resolve()):
            return m.group(0)
        return f"]({_blob(config, resolved)}{rest})"

    return LINK.sub(sub, markdown)


def on_files(files, config):
    root = _repo_root(config)
    text = (root / "README.md").read_text(encoding="utf-8")
    # README는 레포 루트 기준으로 쓰여 있다: docs/ 안쪽은 사이트 기준으로 당기고,
    # 바깥은 blob URL로 보낸다.
    text = _rewrite(text, config, root)
    text = re.sub(r"\]\(docs/", "](", text)
    files.append(File.generated(config, "index.md", content=text))
    return files


def on_page_markdown(markdown, page, config, files):
    base = (Path(config.docs_dir) / page.file.src_uri).parent
    return _rewrite(markdown, config, base)
