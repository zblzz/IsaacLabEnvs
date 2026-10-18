# 服务器训练，本地验证与查看

两种方式共用一套项目代码、实验目录和录制接口。仿真模块负责场景与图像；项目 task 负责评估指标；算法 adapter 负责加载 checkpoint 并生成动作。

| 你要做的事 | 执行位置 | 本地需要什么 |
| --- | --- | --- |
| 看 MP4 | 服务器运行仿真并编码，本地播放文件 | 视频播放器；不需要 Isaac Sim |
| 看已记录的三维运动、更换视角 | 本地运行状态回放 | 兼容的 NVIDIA RTX GPU、同版本运行环境与资产 |
| 重新验证策略、施加扰动 | 本地或服务器运行项目 evaluate | 项目算法、匹配的代码/配置/资产/权重 |
| 远程交互 | 服务器运行仿真，本地接收 WebRTC | Streaming Client 和可达的视频网络链路 |

状态回放按帧覆盖物理状态，所以外力不会改变后续记录。它不执行策略，不能计算新的策略成功率。真正的扰动测试必须运行项目 evaluate。视频录制不自动上传任何服务。

## 文件约定

沿用 `outputs/`，不另建一套 logs 管理框架。已有算法使用 `logs/` 也可以，在同步配置里指定它即可。

```text
project/
  isaacLabEnvs/                  # 可复制的仿真依赖，不含数据集、任务或算法
  tasks/、algorithms/、adapters/、assets/、dataset/、configs/  # 宿主项目拥有
  outputs/
    experiment-001/              # 已完成的一次运行，封存后不再改
      params/                   # 项目写出的实际 task/agent 配置
      checkpoints/              # 显式选定的策略及必要的基础模型
      experiment.json           # 项目参数、观测/动作定义、关节顺序等
      result.json               # 验证指标，或明确标为 physics smoke
      trace.npz                 # 可选：状态序列
      trace.scene.yaml          # 可选：记录时生效的 SceneCfg
      video.mp4                 # 可选：服务器生成的 H.264 视频
      manifest.json             # 代码、输入、产物与镜像的校验清单
```

`manifest.py` 不规定算法的 checkpoint 格式。项目要保存模型依赖的全部文件，包括归一化统计量、残差策略基础模型、tokenizer 等。`experiment.json` 中需要说明观测字段及顺序、动作缩放与坐标系、关节名称顺序、控制频率；有 VLA 时再记录图像预处理、动作块和历史窗口。这些语义由项目定义，不能从 `.pt` 扩展名推断。

Git 同步代码和小配置；资产与 dataset 按需单独准备，保留项目内部相对位置。同步脚本只同步指定的实验，不自动下载整个 dataset，也不递归收集 USD/URDF 的外部依赖。资产清单应涵盖实际使用的网格、材质和纹理，不能只选顶层 URDF。

## 方式 A：服务器录制，本地直接看

以下命令在模块根目录执行。先用不需要数据集的方块例子确认通路：

```bash
python docker/run.py run -- \
  --num-envs 1 --steps 120 \
  --output outputs/drop-demo/result.json \
  --record outputs/drop-demo/trace.npz \
  --video outputs/drop-demo/video.mp4
```

服务器无需桌面。`--video` 自动启用离屏渲染；`--steps` 是控制步数。此例控制周期 0.02 秒，默认 `--video-every 2`，因此视频 25 FPS、时长 2.4 秒。录像时长由仿真时间决定，不等于实际等待时间。调大采样间隔可降低录制开销；相机位置、目标点与分辨率在场景 YAML 中设置。

`--record` 同时生成 `trace.scene.yaml`，包含命令行覆盖后的环境数量和完整场景参数。资产路径相对于这份 YAML 保存；两台机器的项目绝对路径可以不同，但项目内的相对目录关系要保持一致。它不会复制资产。

通过 Remote-SSH 打开 `video.mp4`，若编辑器的视频预览不可用，就下载后用本地播放器打开。Mac 不需要安装 CUDA 或 Isaac Sim。

已有轨迹也能在服务器补录视频：

```bash
python docker/run.py run --script scripts/replay.py -- \
  --config outputs/drop-demo/trace.scene.yaml \
  --trace outputs/drop-demo/trace.npz \
  --video outputs/drop-demo-replay.mp4
```

## 方式 B：同步后在本地 RTX 机器运行

当前 Docker 启动器针对 Linux 和 X11。Windows/WSL 的本地 GUI 不在本次验收范围；Mac 可用上面的文件播放或下面的远程流式方式。

1. 在服务器固定本次实验使用的代码版本，完成运行后封存配置、权重和输入。训练期间不要修改该 checkout 的相关代码；清单是在封存时生成的，无法追溯训练途中发生的编辑。
2. 本地检出同一份代码，并准备匹配的运行镜像和资产。不要仅以两个镜像 tag 一样判断版本相同；清单可比较镜像 ID。自行重建若产生不同 ID，先核对差异，或使用同一份导出的镜像。
3. 在本地复制 `configs/sync.example.json` 为 `configs/sync.local.json` 并填写：

```json
{
  "host": "research-server",
  "remote_root": "/server/project/outputs",
  "local_root": "../outputs"
}
```

`host` 是你的 SSH 配置别名或 `user@hostname`；SSH 端口、私钥、跳板机写在 `~/.ssh/config`。`local_root` 相对于同步配置文件，故上例对应项目根目录的 `outputs/`。两端需安装支持 `--protect-args` 的 rsync；老版 macOS 自带 rsync 可能需要更新。

```bash
# 在本地执行；dry-run 仍会连接服务器，但不传文件
python scripts/sync.py --config configs/sync.local.json --run drop-demo --dry-run
python scripts/sync.py --config configs/sync.local.json --run drop-demo

# 只有 MP4、PNG、JSON，不拉权重或轨迹；适合 Mac
python scripts/sync.py --config configs/sync.local.json --run drop-demo --mode media
```

同步保留目录结构，支持重试，不使用 `--delete`。同名目标文件会按 rsync 更新规则被替换，因此实验名称应唯一，不要把本地产物写入同名服务器实验。完整模式默认排除 TensorBoard events 和临时文件；需要曲线时自行同步 events。不要同步正在写入的 checkpoint；训练框架应先写临时文件，再原子重命名。

4. 在本地校验实验，然后启动窗口。这里的路径仍是模块根目录下的相对路径：

```bash
python scripts/manifest.py check --project . --run outputs/drop-demo
python docker/run.py run --gui --script scripts/replay.py -- \
  --config outputs/drop-demo/trace.scene.yaml \
  --trace outputs/drop-demo/trace.npz --env-index 0 --loop
```

`--env-index` 选择原始并行环境中的一个；`--loop` 循环播放直到关闭。要重新执行策略，改用项目的 evaluate 入口和显式 checkpoint，不能用此状态回放入口。

## 如何封存与校验

方块示例完成后，在服务器执行（之后再进行上面的同步）：

```bash
python scripts/manifest.py create --project . --run outputs/drop-demo \
  --input configs/drop.yaml --image isaaclab-envs:2.3.2
```

清单自动记录当前模块的 `env/`、`scripts/`、`docker/` 和 `pyproject.toml` 内容哈希；额外 `--input` 由项目显式列出任务、算法、adapter、配置及所用资产/数据文件，可重复传入。所有 input 路径相对于 `--project`；不可跨出项目根目录，也不能包含正在封存的 run。共享仿真模块的路径不必在项目内，它会单独校验。

所有 run 文件也会记录 SHA256；`--contract experiment.json` 可附带项目接口描述；`--image` 会记录实际 Docker image ID。Git commit 和 dirty 状态用于追踪，内容校验仍以明确选取的文件为准。校验不等于动力学一致性或策略效果证明，也不会执行 checkpoint。纯宿主工具只需要 Python 3.11+；只看视频无需运行镜像校验。

未声明的外部数据不在校验范围。不要把整套巨大数据集列为 input；选择本次验证用到的 clip、索引或数据版本清单。配置中的绝对路径需要由项目 adapter 改为本地路径，工具不会猜测和替换任意 JSON/YAML 中的字符串。

封存后不要往同一个 run 追加本地评价结果。新结果写另一个目录，否则完整性校验会提示新增文件。清单与完整同步使用相同的 TensorBoard events / 临时文件排除规则。建议将选定 checkpoint 和所需配置整理进独立的完成目录，避免同步所有早期权重。

## ManipTrans 与 DexGrasp 的历史接入示例

这些入口属于宿主项目，不包含在本模块中；它们是历史接口记录，使用前需确认对应项目移植代码仍然存在。复制本模块不会生成这些入口。

ManipTrans 已有 `evaluate --checkpoint ... --video ...`，录像 adapter 现在复用通用 `Video`。在 ManipTrans 项目根目录运行以下形式，路径占位符替换为训练时匹配的文件：

```bash
python maniptrans_lab_envs/tools/container.py run -- evaluate \
  --motion <本地验证clip.npz> \
  --dynamics maniptrans_lab_envs/configs/inspire_native.yaml \
  --stage residual --checkpoint <本次checkpoint.pth> \
  --base-checkpoint-rh <匹配的基础策略.pth> \
  --num-envs 1 --episodes 2 \
  --output maniptrans_lab_envs/outputs/evaluation-001 \
  --video maniptrans_lab_envs/outputs/evaluation-001/video.mp4
```

参数必须匹配训练的 stage、手和控制配置；双手还需 `--sides rh lh` 和左手基础策略。服务器直接运行上述命令即可离屏录制；本地交互时在 `run` 后加 `--gui`。这个入口是项目自己的实现，并不是官方 rsl_rl 的 `play.py`，不自动读取任意 `params/env.yaml`。`experiment.json` 已保存参数和接口描述，但尚无通用的一键恢复任意算法配置机制。

DexGrasp 的 `isaaclab_integration/scripts/smoke.py` 新增同样的 `--video 路径.mp4`；默认每 4 个 100 Hz 控制步录一帧，即 25 FPS。目前迁移范围仍是物理 smoke，尚无 Isaac Lab 策略 evaluate；不能把 smoke 视频称为原论文策略复现。

## 可选：WebRTC 远程交互

已按当前 2.3.2 镜像 AppLauncher 源码加入 `Runtime(livestream=2)`，以及通用 smoke/replay 的 `--livestream 2` 参数。这里 2 是内网模式，默认 0 关闭。运行示例：

```bash
python docker/run.py run --script scripts/replay.py -- \
  --config outputs/drop-demo/trace.scene.yaml \
  --trace outputs/drop-demo/trace.npz --livestream 2 --loop
```

无需 `--gui`、X11 或服务器桌面。本地使用与 Isaac Sim 5.1 兼容的 **Isaac Sim WebRTC Streaming Client** 连接服务器内网地址。此版本官方文档推荐该客户端，不能把旧版浏览器客户端或旧 Omniverse Streaming Client 的说明直接套过来。

服务器需具备兼容的渲染 GPU 和 NVENC。官方 5.1 文档列出 TCP 49100 和 UDP 47998；普通 SSH `-L` 只转发 TCP，不能代替完整的媒体链路。先使用同一局域网，或已配置且允许相应流量的 VPN，再检查实际连接。当前 Docker 使用 host network；启动器不会修改防火墙，也不会安装 VPN 或远程桌面。

参考：[Isaac Sim 5.1 Livestream Clients](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/manual_livestream_clients.html)。客户端连接、跨网络传输和鼠标扰动物理交互尚需在用户实际两台机器上验证。录像已可独立使用，不依赖这一步。

W&B 可以由项目的训练/评估 logger 在完成视频后上传；通用环境不依赖 W&B，也不承诺所有框架的 `--logger wandb --video` 都自动上传。NoMachine / Sunshine 属于机器部署层，不放进 env，也不作为本模块必需组件。
