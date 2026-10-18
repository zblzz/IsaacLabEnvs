# IsaacLabEnvs

可迁移的 Isaac Lab 仿真模块：加载机器人与场景，提供物理控制、状态、接触和回放。任务、算法与数据集由宿主项目管理。

## Quick Start

需要 Linux、NVIDIA GPU 驱动、Docker 和 NVIDIA Container Toolkit。固定 Isaac Lab 2.3.2 / Isaac Sim 5.1。

在本目录执行：

```bash
python3 docker/run.py build   # 首次构建；已有镜像可跳过
python3 docker/run.py run     # 方块落地 smoke，报告：outputs/smoke.json
```

## 服务器验证并保存 MP4

```bash
python3 docker/run.py run -- --video outputs/smoke.mp4
```

使用默认方块场景：4 个环境、120 步，无窗口运行，生成约 2.4 秒视频。检查 `outputs/smoke.json` 中 `finite: true`、`video_frames: 60`，并打开 MP4 查看。

本地 X11 窗口查看：

```bash
python3 docker/run.py run --gui
```

## 配置与迁移

```text
isaacLabEnvs/
├── env/         # 仿真接口与 Isaac Lab 后端，import isaaclab_envs
├── assets/      # robots、objects、scenes、materials
├── configs/     # 机器人、灯光、渲染、布局及组合示例
├── scripts/     # smoke、录像、回放和同步
├── docker/      # 运行环境
├── tests/       # 验证
└── docs/        # 详细说明
```

机器人、材质和灯光通过 YAML 的 `ref` 独立引用，由场景组合。内置 Franka FR3、UR5、Allegro、Barrett、Shadow Hand 和 G1；基础场景位于 `configs/assets/<名称>.yaml`。

迁移时将整个 `isaacLabEnvs/` 复制到项目根目录，排除 `.git/`、`.cache/`、`outputs/` 和 Python 缓存。任务、算法、数据集保留在模块外。代码和配置更新无需重建镜像；运行依赖变化时再构建。

## 详细文档

- [配置组合：更换机器人、材质与灯光](docs/configuration.md)
- [项目接入：目录边界与控制接口](docs/integration.md)
- [录像、回放与服务器同步](docs/remote-workflows.md)
- [渲染参数与画质](docs/rendering.md)
- [默认资产与许可](assets/README.md)
- [开发检查与验证记录](docs/validation.md)
- [维护约定](AGENTS.md)
