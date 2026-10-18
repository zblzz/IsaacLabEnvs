# IsaacLabEnvs：维护说明

## 目的

这是一份独立、可迁移的 Isaac Lab 物理场景模块，不是某篇论文的任务实现，也不是训练框架。干净分发不包含 ManipTrans / DexGrasp 的任务、算法、学习权重或数据集；包含独立的默认机器人、桌面和三个物体，用于迁移验证。用户入口与可执行命令以 `README.md` 的 Quick Start 为准；修改行为时同步更新文档。

## 阅读顺序

1. `README.md`：启动、查看和迁移。
2. `env/config.py`：完整配置字段。
3. `env/contracts.py`：控制和状态重置约定。
4. `docs/integration.md`：任务、算法、adapter 的边界。
5. `env/isaaclab/backend.py`、`assets.py`：后端实现。
6. `tests/physics_contract.py`：实际物理语义的验收标准。

## 结构和依赖方向

- `env/` 安装为 `isaaclab_envs`，避免与宿主项目已有 `env` Python 包冲突。
- `env/isaaclab/` 封装 Lab、PhysX、USD；配置和公共契约可在未启动模拟器时导入。
- 模块不创建 dataset、tasks、algorithms 或项目 adapters；它们由宿主项目管理，位于本目录外。复制集成时整个 `isaacLabEnvs/` 放在宿主项目根目录，不把宿主内容混入该目录。
- 项目 `tasks/` 使用物理状态定义目标、观测、奖励、终止和 reset 分布。
- 项目 `algorithms/` 负责模型、损失、优化与 checkpoint。
- 项目 `adapters/` 负责数据格式、名称/坐标映射、动作解码及 RL/VLA 框架包装。
- 禁止后端反向导入项目任务、算法或数据集；不要用项目名分支解决兼容问题。
- `assets/{robots,objects,scenes,materials}` 存仿真资源和共享视觉材质；`.cache/` 存可重建转换结果；`outputs/` 存运行结果。
- 机器人按 `assets/robots/{arm,hand,humanoid}/<name>` 分目录。默认目录、型号与预设在 `assets/catalog.json`；所有网格/纹理依赖必须在分发目录内，禁止依赖开发机器上的绝对路径或旧项目软链接。
- `scripts/sync.py`、`manifest.py` 是只依赖宿主 Python 标准库的实验传输/校验工具；不能导入 Isaac Sim 或算法。使用流程见 `docs/remote-workflows.md`。

## 运行环境

固定官方 `nvcr.io/nvidia/isaac-lab:2.3.2`。Python 由 `/isaac-sim/python.sh` 启动。Docker 构建安装 SHA256 校验的 importer 2.4.31，不依赖 CHORD 或论文项目镜像。

宿主机运行 Docker 启动器与 Git 操作；仿真、测试和项目 Python 入口在容器内运行。启动器使用宿主 UID/GID，并通过命令参数、配置文件和挂载路径传参。环境变量只用于容器运行所需的 HOME、EULA、显示认证，不能用来隐藏实验配置。

一进程一个 Runtime / Scene；先启动 Runtime，再导入后端。退出时释放 Scene，然后关闭应用。发生异常必须打印并返回非零状态，不能把 Kit 退出码 0 当作 smoke 成功；验收需检查报告和断言。

## 不可含糊的物理约定

- SI 单位：m、s、kg、N、N·m；转动关节 rad，移动关节 m。
- 公共姿态四元数 `xyzw`；后端负责转换 Lab 的 `wxyz`。
- root/body 位置相对于各环境原点；姿态和速度沿世界轴，世界力作用于所选刚体 COM。
- `physics_dt` 是物理步长；`decimation` 个物理步组成一个控制步。
- Command 是物理控制目标，归一化、残差叠加、动作块、滤波属于项目 adapter/controller。
- 世界系外力每个物理子步重写，使用 instantaneous wrench composer，不能缓存过期姿态。
- `reset(env_ids=...)` 只重置指定环境的物理状态。奖励、成功率、episode 计数和 autoreset 属于 task。
- `state()` 返回拥有独立存储的快照；后续 step/reset 不能覆盖已有观测。
- 接触 `net_force` / `pair_force` 单位 N，当前值来自最近物理子步。它们不等于原仿真器逐接触 impulse，也不是整个控制步的冲量积分。
- pair filter 的一个传感器只能选择一个刚体；通过多个具名传感器拓展。物体部件名称必须保留。
- mimic、合并固定关节、质量/惯量修补必须显式配置。源资产只读；转换写缓存。不能静默套用某项目的修补策略。

## 修改原则

优先小而明确的模块和类型化配置。只在输入边界验证必要条件；不要复制重复检查、依赖无穷 fallback 或建立大型注册框架。后端确实缺少能力时才增加公共接口，不为未来猜测功能。

新增物理能力要有能检出错误的测试：例如世界力旋转不变性、不同环境 reset 隔离，而不是只断言函数被调用。检查流程见 README，不启动未经请求的长训练。

新增机器人先检查名称、关节类型/限值、质量/惯量、mimic 和碰撞几何；smoke 通过后才能讨论任务效果。对未经测量的动力学一致性保留明确说明。

修改默认资产时保留上游 LICENSE/NOTICE、固定提交和 source.json 中的改动记录，更新文件 SHA256；先运行 `python scripts/check_assets.py`，再对相应 `configs/assets/*.yaml` 运行 smoke。名称兼容修复放在资源准备阶段并记录映射，不能在后端加入某个机器人专用分支。默认固定基座/无机器人重力的导入验证，不代表机器人动力学、闭环控制或真实硬件参数已复现。

## 远程训练与回放

必须区分项目策略 evaluate、已记录状态回放、RGB 视频播放。状态回放不能用来证明策略成功率或抗扰动性。checkpoint 加载、观测/动作语义、归一化、VLA 预处理都在项目 adapter，不引入所谓通用模型加载器。

视频由 `env/recording.py:Video` 按控制周期采样，帧率跟随仿真时间；不要为名义 30 FPS 改变播放速度。默认训练不启用渲染；录像在独立验证进程进行。文件关闭后再同步。

记录有效配置，使用相对于 YAML 的资产路径，保持跨机器的项目相对布局。清单记录模块代码、显式项目输入、完整实验产物及可选镜像 ID；它不复制资产、不自动恢复未声明依赖，也不能追溯训练中途的代码变更。封存实验保持不变，本地新结果写新目录。

同步必须显式选择 run，不猜最新 checkpoint、不默认传整个 dataset、不使用 rsync --delete。W&B 上传、Git push、SSH 目标和网络设置由用户明确配置；不把账号、IP 或实验参数藏进环境变量。Livestream 默认关闭，仅显式传参开启；未验证客户端连接时不能声称远程交互已跑通。

## 场景外观

配置组合由 `env/presets.py` 统一完成。`configs/robots` 只定义模型、导入、初始关节和驱动/求解参数；摆放、固定基座/重力选择、材质、灯光由场景决定。材质库在 `assets/materials`，灯光和渲染在 `configs/lighting`、`configs/rendering`，通用布局在 `configs/scenes`，可执行组合在 `configs/assets`。新增示例优先引用，不复制已有机器人和布局。

`ref` 及资源路径均相对于声明它的文件。普通映射递归覆盖；显式新 `ref` 替换该节点的旧预设后应用同级覆盖，避免新机器人继承旧关节或新材质继承旧贴图。解析不导入模拟器；未知字段由配置类型拒绝。`save_scene` 必须保存展开后的有效参数并将资源路径相对化，不能把易变的预设引用写入录制快照。详见 `docs/configuration.md`。

`LightingCfg` 和 `VisualMaterialCfg` 属于可序列化场景配置；原生实现集中在 `env/isaaclab/appearance.py`。光照与可选外观覆盖不能改写源资源或物理材质；无碰撞背景必须显式禁用碰撞。新增展示预设以实际 RTX 截图检查，不能用生成图片代替仿真结果；场景保存/回放应保留灯光和材质配置。

HDR 和材质贴图必须使用相对 YAML 的路径并在 save_scene 中保留；随分发保存许可、来源及摘要。`RendererCfg` 是显式的展示配置，省略时不覆盖 Runtime 的渲染设置；路径追踪静态采样上限不能当作运动视频每帧实际采样数。详见 `docs/rendering.md`。
