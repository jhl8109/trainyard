from setuptools import find_packages, setup

package_name = "ty_teleop"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="jhl8109",
    maintainer_email="jhl81094@gmail.com",
    description="게임패드 텔레오퍼레이션 — joy → end-effector twist → IK → joint_command",
    license="Apache-2.0",
    # colcon 은 이 test 의존성을 보고 pytest 로 테스트할지 정한다.
    # 없으면 조용히 `python -m unittest` 로 내려가 pytest 테스트를 수집하지 못한다.
    # (deprecated 된 tests_require 대신 extras_require — setuptools 78+ 가 경고한다)
    extras_require={"test": ["pytest"]},
    entry_points={
        "console_scripts": [
            # 노드는 각 티켓에서 추가한다.
        ],
    },
)
