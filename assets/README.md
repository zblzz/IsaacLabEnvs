# 默认迁移验证资产

随模块一起复制即可使用，不依赖旧项目、ROS 安装、网络资产服务器或数据集。源 URDF、网格、材质与纹理保留在本目录；首次运行时 Isaac Lab 在 `.cache/assets/` 转换 USD。

```text
assets/
├── catalog.json
├── robots/
│   ├── arm/
│   │   ├── franka/        # FR3 + Franka Hand，7 轴机械臂 + 2 个手指关节
│   │   └── ur5/           # UR5，6 轴；不是 UR5e
│   ├── hand/
│   │   ├── allegro/       # 右手，16 关节
│   │   ├── barrett/       # 8 关节独立描述模型
│   │   └── shadowhand/    # 右手含腕，24 关节独立描述模型
│   └── humanoid/
│       └── g1/            # 宇树 G1，29 关节，橡胶手模型
├── scenes/table/          # 1.2 × 0.8 m 桌面，桌面上表面 z=0.75 m
└── objects/
    ├── cube/             # 边长 0.08 m
    ├── cylinder/         # 半径 0.035 m，高 0.10 m
    └── sphere/           # 半径 0.04 m
```

三个物体均为 0.1 kg，带碰撞体和均匀密度解析惯量；桌子由桌板和四条腿组成，使用五个静态箱体碰撞体。这些 USDA 几何在本项目中生成，不依赖第三方物体数据集。

## 迁移后先运行

在模块根目录执行；第一条只需要宿主 Python 3.11+：

```bash
python scripts/check_assets.py

# 无需机器人，检查桌面、物体、接触和渲染
python docker/run.py run -- --config configs/assets/tabletop.yaml \
  --steps 60 --screenshot outputs/tabletop.png

# 选择一种机器人；其余可用 allegro、barrett、shadowhand、ur5、g1
python docker/run.py run -- --config configs/assets/franka.yaml \
  --steps 60 --output outputs/franka.json --screenshot outputs/franka.png
```

需要本地窗口，在 `run` 后加 `--gui`，并把 `--steps` 增加到 1000。需要服务器录像，将 `--screenshot` 换成 `--video outputs/franka.mp4`。相机位置、机器人位置、驱动参数与初始关节姿态均在对应 YAML 中修改。

展示画质可加 `--rendering-mode quality --resolution 1920 1080`；通用 smoke/replay 默认 balanced。截图会等待额外 32 个纯渲染帧用于降噪稳定。默认几何桌面与纯色物体主要用于验证，不包含写实木纹或摄影棚背景；画面构图仍由 YAML 的 camera_eye / camera_target 决定。

默认机器人验证采用固定基座、机器人重力关闭、PD 保持初始姿态；物体重力开启，落到桌面上。G1 固定骨盆用于检查模型导入，不代表站立或行走控制。自碰撞默认关闭，固定关节合并为刚体；需要逐个固定 link 的任务应显式关闭合并并重新验收。验证预设的 PD 参数不是厂商控制器标定。

Barrett 与 Shadow Hand 的源模型把关节独立描述，不能把关节数量直接等同于真实硬件独立电机数。Franka 保留两个手指间的 mimic 关系。策略 adapter 必须使用 `scene.describe()` 的实际关节顺序，不依赖 URDF 文件顺序。

## 来源与可追踪性

| 资产 | 上游 | 随附许可 |
| --- | --- | --- |
| Allegro / Barrett / Shadow Hand | [dexsuite/dex-urdf](https://github.com/dexsuite/dex-urdf) | 各目录保留其原始 LICENSE；前两者为上游 BSD 风格声明，Shadow 为 Apache-2.0 |
| Franka FR3 | [frankarobotics/franka_description](https://github.com/frankarobotics/franka_description) | Apache-2.0，保留 LICENSE 和 NOTICE |
| UR5 | [ros-industrial/universal_robot](https://github.com/ros-industrial/universal_robot) | 保留 ur_description 的 BSD LICENSE |
| G1 | [unitreerobotics/unitree_ros](https://github.com/unitreerobotics/unitree_ros) | 保留上游 LICENSE |

每个资产目录中的 `source.json` 记录上游提交、原始入口、改动说明和文件 SHA256。机器人版本已固定，运行时不会自动拉最新文件。Xacro 已展开为 URDF，运行时无需安装 ROS 或 xacro。没有修改旧项目中的源文件。

Allegro 的点号名称会触发当前 URDF 导入器的无效 USD 路径问题，因此本地资源统一改为下划线。`robots/hand/allegro/name_mapping.json` 记录关节、link 和文件名映射；几何、质量、惯量、限位与运动学变换未改动。其余说明见各自 source.json。

`check_assets.py` 检查内容哈希、URDF 网格、OBJ/MTL 和 DAE 纹理的本地依赖、配置入口与关节数量；不启动模拟器，也不代替物理 smoke。修改自有资产后应更新对应来源记录，不能通过关闭检查掩盖缺失文件。

摄影棚展示额外包含两份 CC0 资源：`scenes/lighting/photo_studio_01` 的 2K HDR（Sergej Majboroda / Poly Haven），以及 `scenes/materials/blue_metal_plate` 的 1K 粗糙度图（Rob Tuytel / Poly Haven）。原文件不修改；各目录的 `source.json` 记录 URL 和 SHA256。使用预设为 `configs/assets/franka_hdr.yaml`，来源和用法见 `docs/rendering.md`。
