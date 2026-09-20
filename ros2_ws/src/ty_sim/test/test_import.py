"""ty_sim 패키지 import 스모크 테스트 (TY-3).

수집할 테스트가 하나도 없으면 pytest 가 exit code 5 로 끝나 `colcon test` 가
패키지 전체를 실패로 잡는다. 노드가 붙기 전까지 이 파일이 그 자리를 지키고,
동시에 패키지 디렉터리 이름과 import 이름이 어긋나는 것도 잡는다.
"""

import ty_sim


def test_package_imports():
    assert ty_sim.__name__ == "ty_sim"
