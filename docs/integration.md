# 接入任务、算法与新项目

## 项目层与仿真依赖分别做什么

| 层 | ManipTrans 示例 | DexGrasp-Zero 示例 |
|---|---|---|
| tasks | 参考动作帧、跟踪观测、奖励、失败判据、课程与 episode | 抓取目标、接触/几何观测、奖励、成功判定与初态分布 |
| algorithms | PPO、网络、优化器、训练 checkpoint | GNN actor/critic、PPO；未来也可接 VLA |
| adapters | 轨迹文件转状态、基础动作与残差组合、手腕力和关节目标解码、RL-Games 包装 | 原数据格式、关节排列、root guidance、动作增量转目标、RaiSim 风格观测/框架适配 |
| env | 同一个 Scene：资产、接触、物理步进、状态、重置 | 同一个 Scene；支持虚拟根关节，保留物体部件 |

这里的项目名称只是边界说明；干净模块不包含上述任务或算法实现。换算法不等于换任务，换任务也不要求重新写资产加载和物理循环。

```text
项目脚本 → algorithm / policy → adapter.decode → Command
                                      ↓
                    task ← state ← PhysicsScene.step
                     ↓
             reward / done / reset 请求
```

## 接口约定

`SceneCfg` 定义整个向量场景。每个动态实体有名字和元数据；`describe()` 提供 body/joint 的真实顺序和关节限值。`Command.joints` / `bodies` 是精确名称序列，后端只解析一次，随后缓存绑定。

`Command` 可包含关节位置、速度、力矩以及刚体外力/外力矩。所有字段都是带环境维度的 Torch tensor，设备与 Scene 一致。关节命令 `[N,J]`，wrench `[N,B,3]`。关节控制模式由驱动增益决定；纯力矩控制应显式令 stiffness/damping 为零。未提交的关节目标保持之前值；外力只维持本次控制步，下次不提交则消失。

`state()` 返回 `{entity: {root, bodies, joint_position?, joint_velocity?, joint_effort?}, contacts: ...}`。root 为 `[N,13]`：位置3、xyzw4、线速度3、角速度3。body 为 `[N,B,13]`。关节顺序与 `describe()` 一致。

`reset(states, env_ids=...)` 先将所选环境的全部动态实体恢复配置初态，再应用具名 `ResetState` 覆盖。ResetState tensor 第一维是选中环境数，不是总环境数。写入关节位置时，未给速度则置零；`write_state()` 用于指定状态回放，不推进时钟。

task 需要 Gymnasium 风格 `step` 时，在项目侧组合：物理 step → 观测/奖励/终止 → 保存 terminal observation → 只 reset 完成环境 → 返回框架接口。不要让物理模块隐式丢掉终止前状态。

## 新项目要改多少

- 只换同类机器人、物体、桌面布局：资产 + 配置。
- 换跟踪任务为抓取任务：新增 task 的奖励、观测、reset、终止。
- 换 PPO 为 VLA：新增 adapter 的图像预处理、动作解码、动作块执行，物理后端复用。
- 新传感器、软体或特殊约束：需要扩展后端能力，不能声称只改 YAML 就能完成。

当前 RGB 是单个场景相机画面，不是每个环境一个相机的批量视觉观测；暂未实现深度、分割和触觉阵列。物理引擎 API 没有预留假实现，新增时必须明确契约与测试。

## 复制到项目根目录

支持将整个模块作为宿主项目中的独立目录：

```text
my_project/
├── isaacLabEnvs/       # 本模块：env、默认仿真资产、示例配置、Docker、工具
├── tasks/             # 项目观测、奖励、终止、reset
├── algorithms/        # 项目 RL / VLA 模型与训练
├── adapters/          # 项目动作/数据/算法框架适配
├── assets/            # 项目专用机器人、物体和场景
├── dataset/           # 项目拥有，可链接到外部数据盘
├── configs/           # 项目场景、任务和算法配置
├── scripts/           # 项目 train / evaluate / play
└── outputs/           # 项目运行结果
```

上述宿主目录是职责示意，不要求已有项目改名或搬迁。`isaacLabEnvs/` 内不创建 dataset、tasks、algorithms、项目 adapters 或训练入口。模块的示例配置是资产/物理/显示检查，不是算法配置。

以下 `/path/to/my_project` 是待替换的宿主项目根目录：

```bash
rsync -a \
  --exclude='.git/' --exclude='.cache/' --exclude='outputs/' \
  --exclude='__pycache__/' --exclude='*.egg-info/' \
  --exclude='.pytest_cache/' --exclude='.ruff_cache/' \
  /data/sim/isaac/isaacLabEnvs/ /path/to/my_project/isaacLabEnvs/

cd /path/to/my_project
# 该机器尚无镜像时才需要构建。
python isaacLabEnvs/docker/run.py build
python isaacLabEnvs/docker/run.py run --project .
```

启动器定位自己的模块目录，同时挂载宿主项目，并在容器内以 editable 方式安装 `isaaclab_envs`。因此 Python 使用 `from isaaclab_envs import ...`，不需要手动改 `sys.path`，也不是 `import isaacLabEnvs`。

项目已经实现 `scripts/train.py` 后，可从宿主项目根目录启动：

```bash
python isaacLabEnvs/docker/run.py run --project . --script scripts/train.py -- <项目参数>
```

此处 `<项目参数>` 是说明占位符，需替换或删去；本模块不提供这个训练脚本。项目有单独的 Python 包时用 `--install ./包目录`，包需要有自己的安装声明；算法第三方依赖由项目运行镜像安装。外部数据链接使用 `--mount-readonly /外部数据根目录`，不要把数据复制进仿真模块。

复制解决的是仿真代码和资源的迁移。已有任务如果使用别的模拟器，仍需项目 adapter 对齐动作、状态与观测；本模块不会自动把 Isaac Gym/RaiSim 的任务变成 Isaac Lab 任务。

## 材质与场景复用

机器人、材质、灯光和渲染已有独立预设，通过 `ref` 在场景里组合。机器人预设没有场景摆放或外观；`franka_hdr.yaml` 只引用通用摄影棚桌面和 Franka 模型。项目可直接引用同一套预设，不需要复制机器人 YAML 来更换材质。配置语法、替换规则和宿主项目示例见 [配置组合](configuration.md)。后端 `appearance.py` 只负责把有效配置映射到 Isaac Sim，不依赖项目或算法。

## 作为共享依赖

推荐一个维护源，通过 `pip install -e /path/to/isaacLabEnvs` 安装，不在两个项目各维护一份后端。Docker 启动器同时挂载此模块和 `--project` 指定的项目；`--install` 可安装项目自己的轻量 Python 包，`--module` 或 `--script` 选择入口。第三方训练依赖由项目镜像继承本镜像后自行添加。

如果需要完全独立迁移，复制此目录时排除 `.cache/`、`outputs/`、`__pycache__/`、`*.egg-info/`，保留 env、资产目录、配置、Docker 和文档。路径由模块位置、YAML 位置和 CLI 决定，没有绑定原机器的 `/data/...` 路径。

GPU pair-contact filter 的目标需要是受支持的 rigid body。固定桌面若要参与 pair filter，使用 `kind: rigid` 加 `kinematic: true`；纯 `static` collider 不支持该 GPU 过滤路径。没有过滤需求的桌面可继续用 static。

RaiSim 的无质量虚拟关节链、原生 mimic 行为与 PhysX 之间存在模型差异。应在项目 adapter 中显式转换和记录，不要修改通用导入器默认值，也不要将 smoke 的非零接触力当作原论文接触奖励已经对齐。
