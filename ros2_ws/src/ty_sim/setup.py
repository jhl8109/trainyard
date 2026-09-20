from setuptools import find_packages, setup

package_name = "ty_sim"

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
    description="MuJoCo 시뮬레이션 Hardware Interface 노드 — joint_states 퍼블리시 · joint_command 구독 · 카메라 렌더 · 씬 리셋",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            # 노드는 각 티켓에서 추가한다.
        ],
    },
)
