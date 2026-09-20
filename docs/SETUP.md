# 개발 환경 셋업

이 머신(Linux Mint 22.3 = Ubuntu 24.04 noble / RTX 4060 Ti 8GB)에서 TrainYard를 돌리기 위해 설치해야 하는 것들. 릴리즈 순서대로 정리했고, **1단계는 재부팅이 필요하며 이후 모든 GPU 작업의 전제**다.

## 현재 상태 (2026-09-20 점검)

| 항목 | 상태 |
|---|---|
| OS | Linux Mint 22.3 (zena) — Ubuntu 24.04 noble 기반, ROS 2 Jazzy 타깃과 일치 |
| GPU 드라이버 | ❌ nouveau 사용 중. `nvidia-smi` 없음 |
| Secure Boot | disabled — 드라이버 설치 시 MOK 등록 불필요 |
| ROS 2 | ❌ `/opt/ros` 없음 |
| Python | 3.12.3 (시스템) — pip · venv 모두 미설치 |
| 툴체인 | git ✓ / g++ ✓ / cmake ❌ docker ❌ uv ❌ colcon ❌ rosdep ❌ psql ❌ |
| 디스크 | 155GB 여유 |

### Linux Mint 주의점

Mint는 `lsb_release -cs`가 `zena`를 반환한다. ROS 2 · NVIDIA · Docker 저장소는 Ubuntu 코드네임을 요구하므로 **항상 `$UBUNTU_CODENAME`(=`noble`)를 쓴다.** `/etc/os-release`에 이미 정의돼 있다.

```bash
. /etc/os-release && echo $UBUNTU_CODENAME   # noble
```

---

## 1단계 — NVIDIA 드라이버 (v0, 최우선 / 재부팅)

`ubuntu-drivers`가 권장하는 버전은 `nvidia-driver-595-open`이다(README 기재와 일치).

```bash
sudo apt update
sudo apt install -y nvidia-driver-595-open
sudo reboot
```

재부팅 후 검증:

```bash
nvidia-smi                        # 드라이버 · VRAM 8GB 확인
lsmod | grep -E 'nvidia|nouveau'  # nvidia 로드 / nouveau 언로드
```

- 드라이버 패키지가 nouveau를 자동으로 blacklist한다. 수동 설정 불필요.
- Mint GUI(`mintdrivers` → 드라이버 관리자)로 해도 결과는 같다.
- **CUDA Toolkit은 설치하지 않는다.** PyTorch · ONNX Runtime pip 휠이 CUDA 런타임을 번들로 포함하므로 드라이버만 있으면 된다. 직접 CUDA 커널을 컴파일할 일이 생길 때만 고려.

## 2단계 — 빌드 툴체인 · Python 기반 (v0)

```bash
sudo apt install -y build-essential cmake git-lfs \
                    python3-pip python3-venv python3-dev \
                    ffmpeg libgl1 libglfw3 \
                    curl gnupg software-properties-common
git lfs install
```

| 패키지 | 이유 |
|---|---|
| `cmake` | C++ 제어 노드(rclcpp) 빌드. 현재 미설치 |
| `git-lfs` | 체크포인트 · 데이터셋 샘플 |
| `ffmpeg` | LeRobot 데이터셋 포맷이 에피소드를 비디오로 인코딩 |
| `libgl1` `libglfw3` | MuJoCo 뷰어 렌더링 |

Python 패키지 관리자는 `uv`를 쓴다(빠르고 락파일 재현성 확보):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 3단계 — ROS 2 Jazzy (v0)

### 저장소 등록

```bash
sudo add-apt-repository universe          # Mint는 이미 활성화돼 있음
ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infra/ros-apt-source/releases/latest \
  | grep -F '"tag_name"' | awk -F'"' '{print $4}')
curl -L -o /tmp/ros2-apt-source.deb \
  "https://github.com/ros-infra/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo $UBUNTU_CODENAME)_all.deb"
sudo apt install -y /tmp/ros2-apt-source.deb
sudo apt update
```

### 코어 + 개발 도구

```bash
sudo apt install -y ros-jazzy-desktop ros-dev-tools
sudo rosdep init && rosdep update
```

- `ros-jazzy-desktop` — rclcpp/rclpy, RViz2, 데모
- `ros-dev-tools` — colcon, rosdep, vcstool, ament

### 프로젝트에 필요한 ROS 패키지

```bash
sudo apt install -y \
  ros-jazzy-ros2-control ros-jazzy-ros2-controllers \
  ros-jazzy-rosbag2-storage-mcap \
  ros-jazzy-joy ros-jazzy-teleop-twist-joy \
  ros-jazzy-cv-bridge ros-jazzy-image-transport \
  ros-jazzy-xacro ros-jazzy-robot-state-publisher \
  ros-jazzy-kdl-parser
```

| 패키지 | 용도 |
|---|---|
| `ros2-control` / `ros2-controllers` | Hardware Interface 추상화 — 시뮬/실물 교체 지점 |
| `rosbag2-storage-mcap` | MCAP 포맷 기록 (설계 문서 규약) |
| `joy`, `teleop-twist-joy` | 게임패드 텔레오퍼레이션 입력 |
| `cv-bridge`, `image-transport` | 카메라 관측 토픽 |
| `xacro`, `robot_state_publisher` | URDF 기술 · TF 발행 |
| `kdl-parser` | IK 텔레오퍼레이션 (경량). MoveIt은 v0에 과하다 — 필요해지면 `ros-jazzy-moveit` 추가 |

셸 설정 (`~/.bashrc`에 추가하되, 자동 source는 취향에 따라):

```bash
source /opt/ros/jazzy/setup.bash
```

## 4단계 — 시뮬레이션 · 학습 (v0 사이드 → v1)

ROS 2 파이썬 노드와 학습 코드를 **같은 venv에 두려면 `--system-site-packages`가 필수**다. 그래야 venv 안에서 `rclpy`(apt로 설치된 시스템 패키지)가 보인다. 이걸 빼면 파이썬 노드가 import 에러로 죽는다.

```bash
cd ~/orca/trainyard
uv venv --system-site-packages --python 3.12
source .venv/bin/activate
```

```bash
# 시뮬레이션
uv pip install mujoco mujoco-python-viewer

# 학습 (RTX 4060 Ti = Ada, sm_89)
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# 데이터 · 유틸
uv pip install lerobot scipy matplotlib mcap mcap-ros2-support
```

> **OpenCV는 headless만 깔 것.** LeRobot이 `opencv-python-headless`를 의존성으로 가져온다. 여기에 `opencv-python`(full)을 추가하면 두 패키지가 같은 `cv2` 디렉터리를 공유해 충돌하고, 나중에 한쪽을 uninstall하면 **남은 쪽까지 깨진다**(`cv2.__version__` AttributeError). 영상 표시는 `cv2.imshow`가 아니라 ROS 네이티브 도구(`rqt_image_view`, RViz2)를 쓴다.
>
> LeRobot은 `numpy<2.3.0`, `opencv-python-headless<4.14.0`으로 상한을 둔다. 다른 패키지를 설치·재설치한 뒤에는 항상 `uv pip check`로 범위 이탈을 확인한다.

검증:

```bash
uv pip check     # "All installed packages are compatible" 여야 함
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
python -m mujoco.viewer     # 창이 떠야 함 (libglfw3 필요)
```

현재 확정된 버전은 [`requirements.txt`](../requirements.txt)에 고정돼 있다 (`uv pip install -r requirements.txt`).

### 로봇 모델

MuJoCo Menagerie에 **SO-101 모델이 그대로 들어있다** — SO-ARM100으로 대체할 필요가 없다.

```bash
git clone --depth 1 https://github.com/google-deepmind/mujoco_menagerie.git ~/orca/mujoco_menagerie
```

| 경로 | 내용 |
|---|---|
| `robotstudio_so101/scene.xml` | **타깃 로봇.** 6 액추에이터 (`shoulder_pan` `shoulder_lift` `elbow_flex` `wrist_flex` `wrist_roll` `gripper`), sim timestep 0.005s |
| `trs_so_arm100/` | SO-ARM100 (참고용) |

- `--depth 1`로도 2.3GB다. 메시 에셋이 git에 직접 들어있어 LFS는 필요 없다.
- timestep 0.005s = 200Hz 시뮬레이션 → 50Hz 제어 루프당 정확히 4 스텝. 제어 주기 설계가 깔끔하게 나눠진다.

> **8GB VRAM 제약**: ACT 학습은 여유 있지만 SmolVLA급 파인튜닝은 배치 크기 · gradient checkpointing · 혼합정밀도 조정이 필요하다. v5에서 다룬다. 상태 기반 RL(v4)은 비전이 없어 VRAM 여유가 있다.

## 5단계 — 플랫폼 (v1)

PostgreSQL은 호스트에 직접 깔지 않고 Docker로 띄운다. 나중에 Compose 폴리싱(v5)으로 바로 이어진다.

```bash
# Docker Engine + Compose
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER   # 재로그인 필요
```

```bash
sudo apt install -y postgresql-client   # psql만 (서버는 컨테이너)
uv pip install fastapi uvicorn "psycopg[binary]" sqlalchemy alembic pydantic-settings
```

## 6단계 — 추론 최적화 (v2)

```bash
uv pip install onnx onnxruntime-gpu tensorrt
```

- `onnxruntime-gpu`와 `tensorrt` 휠은 필요한 CUDA/cuDNN 라이브러리를 함께 가져온다.
- 양자화 전후 비교는 `onnxruntime.quantization` 사용.

## 7단계 — 실물 로봇 (v3)

```bash
uv pip install feetech-servo-sdk    # SO-101 서보 (STS3215)
sudo usermod -aG dialout $USER      # USB 시리얼 접근, 재로그인 필요
```

- 서보 버스 어댑터용 udev 규칙을 추가해 포트 이름을 고정한다(`/dev/ttyACM*` 순서 변동 방지).
- 하드웨어 주문 시점: **v2 시작 시** (배송 · 조립 리드타임 확보).

## 선택 — 관측 · 편의 도구

```bash
sudo apt install -y nvtop htop tmux ros-jazzy-rqt-common-plugins
```

- `nvtop` — GPU 사용률 · VRAM 실시간 확인 (8GB 한계 추적에 유용)
- [Foxglove Studio](https://foxglove.dev/download) — MCAP rosbag 시각화. 데이터 검증 규칙 만들 때 유용
- GitHub CLI는 이미 설치돼 있다 (CI 작업용)

---

## 순서 요약 / 진행 상황

```
1. nvidia-driver-595-open → 재부팅 → nvidia-smi 확인   ⬜ 미완 ← 블로킹
2. build-essential cmake ffmpeg libglfw3 ...            ⬜ 미완 (sudo 필요)
   uv                                                    ✅ 0.12.17
3. ROS 2 Jazzy (desktop + dev-tools + 프로젝트 패키지)  ⬜ 미완 (sudo 필요)
4. venv + mujoco 3.13 / torch 2.11+cu128 / lerobot 0.6.1 ✅ 완료
   mujoco_menagerie (SO-101 모델 로드·시뮬 검증)         ✅ 완료
5. (v1) Docker + PostgreSQL 컨테이너 + FastAPI           ⬜
6. (v2) onnxruntime-gpu, tensorrt                        ⬜
7. (v3) feetech SDK + dialout + udev                     ⬜
```

sudo 비밀번호가 필요한 단계(1·2·3)는 직접 실행해야 한다. 재로그인이 필요한 그룹 추가(`docker`, `dialout`)는 모아서 한 번에 처리하면 좋다.

드라이버 설치 전까지 `torch.cuda.is_available()`는 `False`다. 이것 자체는 정상이며, 재부팅 후 `True`로 바뀌는지 확인하는 것이 1단계의 완료 조건이다.


