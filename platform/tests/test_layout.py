"""레포 스켈레톤이 무너지지 않았는지 확인하는 스모크 테스트 (TY-2).

여기서 잡으려는 것은 로직 버그가 아니라 **구조 회귀**다 — 패키지 이름과
디렉터리 이름이 어긋나거나, ROS 패키지가 매니페스트 없이 추가되는 경우.
"""

import importlib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ROS_SRC = REPO_ROOT / "ros2_ws" / "src"

SUBPACKAGES = ["sim", "data", "policies", "training", "evaluation", "api"]


def ros_packages() -> list[Path]:
    return sorted(p for p in ROS_SRC.iterdir() if p.is_dir())


def test_trainyard_imports():
    import trainyard

    assert trainyard.__version__


@pytest.mark.parametrize("sub", SUBPACKAGES)
def test_subpackage_imports(sub):
    assert importlib.import_module(f"trainyard.{sub}").__doc__, f"{sub}: 역할 설명이 비었다"


def test_platform_dir_does_not_shadow_stdlib():
    """레포 루트의 ``platform/`` 디렉터리가 표준 라이브러리 ``platform``을 가리지 않는다.

    일반 모듈이 네임스페이스 패키지보다 우선하므로 실제로 가려지지는 않지만,
    ``platform/`` 안에 ``__init__.py``가 실수로 생기면 그 순간 뒤집힌다.
    """
    import platform as stdlib_platform

    assert hasattr(stdlib_platform, "machine")
    assert not (REPO_ROOT / "platform" / "__init__.py").exists()


@pytest.mark.parametrize("pkg", ros_packages(), ids=lambda p: p.name)
def test_ros_package_manifest_matches_directory(pkg):
    manifest = pkg / "package.xml"
    assert manifest.is_file(), f"{pkg.name}: package.xml 없음"

    root = ET.parse(manifest).getroot()
    assert root.findtext("name") == pkg.name
    assert root.findtext("license"), f"{pkg.name}: license 태그가 비었다"

    build_type = root.findtext("export/build_type")
    assert build_type in {"ament_python", "ament_cmake"}

    if build_type == "ament_python":
        assert (pkg / "setup.py").is_file()
        assert (pkg / "resource" / pkg.name).is_file(), "ament_index 마커 파일 없음"
        assert (pkg / pkg.name / "__init__.py").is_file()
    else:
        assert (pkg / "CMakeLists.txt").is_file()
