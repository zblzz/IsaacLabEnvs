# 本机验收范围（2026-10-18）

## 开发检查命令

在模块根目录执行：

```bash
python3 docker/run.py run --module pytest -- tests -q
python3 docker/run.py run --script tests/physics_contract.py
```

第二条启动 GPU 仿真，验证世界系外力、批量环境坐标、部分重置、外力清除与状态快照。检查通过不代表任务或策略复现成功。

运行环境：NVIDIA RTX 3090，官方 Isaac Lab 2.3.2 基础镜像，独立构建的 `isaaclab-envs:2.3.2`。

| 检查 | 规模 | 结果 |
|---|---|---|
| ManipTrans 单手 | 16 环境 × 120 步 | 有限状态/奖励，数值异常 0，240 次任务 reset |
| ManipTrans 双手 | 16 环境 × 120 步 | 有限状态/奖励，数值异常 0，235 次任务 reset |
| ManipTrans RL 适配器 | 16 环境 × 24 步 | 72 维原动作 → 36 维物理命令，48 次 reset，异常 0 |
| DexGrasp-Zero Inspire | 4 环境 × 120 步 | 18 关节响应、部分 reset、保留 top/bottom、非零 pair-contact |
| 公共物理契约 | 4 环境 | 旋转刚体世界力、SI 单位、环境坐标、部分 reset、快照与外力清除 |
| 迁移到全新目录 | 4 环境 × 120 步 | 未挂载论文项目，独立运行通过，env 源码字节一致 |
| 状态轨迹回放 | 120 帧 | 无 pickle 的 NPZ 读取、单环境回放、960×720 RGB 图片通过并人工检查 |
| 单元测试 | 两个测试目录 | 34 通过，1 项因纯 Python 测试未启动 USD 而跳过 |

这些检查没有训练策略，没有重新验证论文成功率。DexGrasp 的奖励、root guidance、原策略观测和 PPO 未在本次移植；其无质量链接修补和缺失限值已在项目报告中逐项记录。接触力不代表原 RaiSim 的逐接触 impulse 已对齐。

首次 RGB 检查曾受主机内存压力阻塞，停止后重试成功。默认 Runtime 采用 performance 渲染和 8 个 Kit 工作线程；纯物理测试不加载相机。机器内存紧张时先运行无截图的 Quick Start。

原始报告、日志、图片与源码指纹保存在同机兄弟目录 `isaacLabEnvs-validation/`，不属于可迁移模块，也不是运行依赖。
# 远程工作流补充验收（2026-10-18）

本轮新增视频、实验同步、校验与路径搬迁检查，产物在 `/data/sim/isaac/isaacLabEnvs-validation/workflows/`。此前本文件的物理验收记录仍属于其原始代码版本；当前发行源码哈希另见 workflows/source_manifest.json。

| 检查 | 结果 |
| --- | --- |
| 通用方块服务器录像 | 1 环境 × 60 控制步；H.264、960×720、30 帧、25 FPS、1.2 秒 |
| ManipTrans 单手录像 | 1 环境 × 60 步；0 数值异常；1280×720、30 帧、30 FPS、1 秒 |
| DexGrasp 物理 smoke 录像 | 1 环境 × 60 步；有限状态，虚拟腕位移 0.00824 m，物体/桌面接触有效；15 帧、25 FPS、0.6 秒 |
| 迁移目录后回放 | 模块复制到另一绝对路径，真实 rsync 传实验，manifest 校验通过；回放 60 帧并输出 30 帧 MP4 |
| 文件传输 | 本机 rsync 验证完整/媒体筛选、路径空格、保留本地文件；未连接另一台服务器 |
| 自动检查 | 模块 8 passed / 1 skipped（容器无 rsync，已另在宿主实测）；ManipTrans 30 passed / 1 skipped（无应用启动时 pxr 不可用） |
| 不一致检测 | 关节顺序所在源码改动、checkpoint 字节改动均被拒绝；配置快照资产路径迁移测试通过 |
| 视频 | 四个视频均用 ffprobe 检查参数、ffmpeg 完整解码；项目中间帧已查看 |

Docker 已重建，视频依赖导入验证通过；当前镜像 ID 为 `sha256:8926256a48c94333e532d889780fcfe0110c29e6678bc7d6525755e834adf7e8`。本轮初始方块录像使用重建前同版本运行依赖镜像；清单记录封存时的镜像，不能替代训练启动时的环境追踪。

首次 ManipTrans 2 环境录像停留在初始化约三分钟，未生成结果，主动停止；改为 1 环境重试完成。未确定首次停滞原因，因此本轮只验收单环境录像，不声明并行场景录像已通过。图像使用 performance 模式，预览有明显噪点，未做论文画质验收。

没有启动训练，没有用学习后的 checkpoint 做新后端效果验收。未实测本地 GUI、跨机 SSH 或 WebRTC 客户端；WebRTC 参数已对照当前镜像 AppLauncher 和官方 5.1 文档核对，不能据此声称远程交互已跑通。
# 默认资产补充验收（2026-10-18）

新增 Allegro 右手、Barrett、Shadow Hand 右手、Franka FR3 + Hand、UR5、宇树 G1 29 DOF，另有程序化桌面、方块、圆柱和球。

六种机器人各完成单环境 60 个控制步的真实 GPU smoke 并生成截图；实际关节数分别为 16、8、24、9、6、29。检查有限状态、正刚体质量、有限关节限位与物体接触；已查看六张机器人渲染图。桌面独立配置也完成同样的 smoke。运行采用固定基座、机器人重力关闭和初始姿态保持，不验证学习策略、抓取成功率或 G1 站立控制。

资源静态检查覆盖 10 项资产的文件 SHA256、URDF 网格、OBJ/MTL/DAE 依赖及关节数。完整模块复制到另一绝对路径后，10 项检查仍通过；副本重新转换并执行 FR3 的 60 步 smoke、截图成功，未挂载原始模块或旧项目。

Allegro 初次导入因点号网格名称产生无效 USD 路径；规范化资源中的名称并写入映射后重试通过，未修改通用后端。最终各资产日志无 Error/Traceback；部分无视觉几何的虚拟 link 仍有导入器空 visual 引用警告。截图使用 performance 渲染，未做论文图像质量验收。

报告、截图、原始日志与目录迁移记录保存在 `/data/sim/isaac/isaacLabEnvs-validation/default-assets/`；`summary.json` 是汇总。具体型号、来源与使用方法见 [默认资产说明](../assets/README.md)。

### 中性灰展示预设

`configs/assets/franka_studio.yaml` 已在本地 Isaac Lab 2.3.2 容器、RTX 3090 上完成 1 环境、60 控制步、quality 渲染；输出 `outputs/franka_studio.png`（1600×1200）与 `outputs/franka_studio.json`。实际查看截图确认白色机器人轮廓和方向阴影可见。报告 finite、subset_reset、snapshot_ownership 均通过，最大接触力约 39.238 N。配置测试 5 项通过，包括灯光/视觉材质跨目录保存读取。未验证服务器渲染或 GUI。原机器人与物体物理参数保留；新增背景禁用碰撞，桌面仅覆盖视觉材质。

### HDR / OmniPBR 展示与回放

本地 RTX 3090、Isaac Lab 2.3.2：`franka_hdr.yaml` 实测完成单环境 60 控制步，路径追踪截图 `outputs/franka_hdr.png`，报告 `outputs/franka_hdr.json`，状态 `outputs/franka_hdr.npz` 和有效配置 `outputs/franka_hdr.scene.yaml`。配置为 16 spp/frame、累计上限 128、6 次反弹；输出 1600×1200。有限状态、部分 reset 和快照检查通过，最大接触力约 39.238 N。

从导出的有效配置和轨迹运行 `scripts/replay.py --renderer realtime --rendering-mode quality`，60 帧回放通过，截图 `outputs/franka_hdr_realtime.png`。两张图已实际查看。导出的 HDR/粗糙度图路径成功解析；没有验证另一台服务器或 GUI。单元测试 9 passed、1 skipped（容器未装 rsync，相关宿主同步测试跳过）；12 项内置资源的完整性检查通过。

### 配置模块化与引用组合

六种机器人、共享材质、灯光、渲染和桌面布局已拆成独立预设。重构前后的 9 个现有场景展开后逐字段一致；没有改变原物理或显示参数。配置测试共 13 passed、1 skipped（容器缺少 rsync），覆盖跨文件资源路径、深层覆盖、更换机器人不残留旧关节、循环引用、展开快照与路径迁移。12 项资产完整性检查通过。

短 GPU smoke：本地 RTX 3090、Isaac Lab 2.3.2，`franka_hdr.yaml`，1 环境 × 60 控制步，quality + realtime，1600×1200。有限状态与快照检查通过，最大物体接触力约 39.238 N；已检查实际截图。单环境的 reset 检查不构成多环境隔离验证。

产物：`outputs/presets_smoke.json`、`outputs/presets_smoke.png`、`outputs/presets_smoke.npz` 和展开后的 `outputs/presets_smoke.scene.yaml`。本轮不重复六机器人 GPU 验收、不运行训练，也未验证远端服务器或 GUI。
