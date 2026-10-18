# 灯光、材质与离线展示

## 采用了哪些参考

- 本地 `video_to_data/robotic_grounding` 的 `tasks/scene_utils/apply_scene_config.py`：支撑面使用深灰、metallic=0.7；本模块将参数留在 YAML，不引用其任务代码。
- 同项目的 `tasks/scene_utils/visual_dr.py`：HDR 池包含 Photo Studio 01；`scripts/rsl_rl/domain_randomization.py`：区分金属、塑料、陶瓷的粗糙度/金属度。这里采用固定参数，不引入随机化。
- 同项目的 `rendering/config.py`：提供路径追踪、采样和反弹次数的配置类型。这只能证明有对应配置，不能据此声称所有 CHORD 入口已启用它；本模块另行实现并实际验证。
- [NVIDIA RoboLab 的 HDR 背景配置](https://github.com/NVlabs/RoboLab/blob/main/docs/background.md)：DomeLightCfg + HDR 贴图，示例强度 500。
- [NVIDIA 的合成数据工作流](https://github.com/NVIDIA-AI-IOT/synthetic_data_generation_training_workflow/blob/main/palletjack_sdg/standalone_palletjack_sdg.py)：OmniPBR 的表面颜色、粗糙度和金属度。
- [Isaac Sim 5.1 材质示例](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/replicator_tutorials/tutorial_replicator_isaac_randomizers.html)：MDL OmniPBR、投影 UV 与材质输入。
- [RTX 路径追踪参数](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_pt.html)：区分每帧采样数和累计采样上限。

实现针对镜像中实际安装的 Isaac Lab 2.3.2 / Isaac Sim 5.1 API，没有直接照搬新版本接口，也不依赖 CHORD 的 vMaterials 大包。

## 使用

在模块根目录执行静态展示：

```bash
python docker/run.py run -- --config configs/assets/franka_hdr.yaml \
  --steps 60 --rendering-mode quality \
  --screenshot outputs/franka_hdr.png
```

本预设使用摄影棚 HDR、OmniPBR、表面粗糙度贴图、45 mm 全画幅相机和路径追踪。机器人原有分部件材质保持不变。物理模型、质量、摩擦与原 Franka 预设相同；背景无碰撞。

日常窗口交互改用实时渲染：

```bash
python docker/run.py run --gui -- --config configs/assets/franka_hdr.yaml \
  --steps 3000 --rendering-mode quality --renderer realtime
```

服务器录像也建议 `--renderer realtime --video outputs/franka_hdr.mp4`，不加 `--gui`。`--rendering-mode quality` 是 Lab 的实时质量档位；`--renderer path_tracing` 是另一种渲染算法，两者不能混为一谈。路径追踪截图静止后积累采样，运动视频每帧不保证达到静态截图的累计采样数。

## 配置边界

外观参数已拆为独立预设：`assets/materials/*.yaml`、`configs/lighting/*.yaml` 和 `configs/rendering/*.yaml`。`configs/scenes/tabletop_hdr.yaml` 组合桌面与外观，`configs/assets/franka_hdr.yaml` 只添加机器人。更换材质或机器人不需要复制整份场景，引用和覆盖示例见 [配置组合](configuration.md)。下列字段表示引用展开后的有效配置。

- `lighting.environment_texture`：相对 YAML 的本地 HDR 路径；`ambient_intensity` 缩放 HDR，`environment_quaternion` 用 xyzw 旋转环境；`environment_visible: false` 只隐藏相机直视的天空，环境仍参与照明和反射。
- `lighting.key_intensity`：本预设设为 0，避免方向光和 HDR 内的灯光形成重复主光。
- `visual_material.shader: omnipbr`：使用镜像内置 OmniPBR.mdl。可配置颜色、粗糙度、金属度。省略整个 `visual_material` 保留源资产材质。
- `roughness_texture`：以 raw 数据读取的本地粗糙度图；`roughness_texture_weight` 混合常量和纹理，`texture_scale` 控制投影尺度。本预设只取 Blue Metal Plate 的粗糙度，没用其蓝色贴图，不代表对该扫描材质的完整复原。
- `renderer`：显式指定渲染算法。展示预设关闭自动曝光，使用 ACES；每帧 16 samples，累计上限 128，最多 6 次反弹，启用 OptiX 降噪。提高累计上限时应相应增加 `--screenshot-frames`；这些额外渲染不推进物理。
- `camera_focal_length`：mm。使用独立 OverviewCamera、36 mm 水平画幅，避免编辑器相机覆盖焦距。省略时保持旧的 viewport 相机行为。

HDR 与粗糙度贴图已下载到 `assets/scenes/lighting` 和 `assets/scenes/materials`，保留来源、作者、CC0 许可与 SHA256，并纳入 `scripts/check_assets.py`。新路径会随 `save_scene` 写成相对路径；复制模块时需要带上这些资源，不需要运行时下载。

当前三种物体和桌子仍是简单几何体，未增加倒角、紧固件或装配件。真实感不仅由渲染参数决定；此预设改善照明、反射、表面变化和镜头，不应宣称与照片无法区分。
