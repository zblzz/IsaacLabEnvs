# 组合机器人、材质和场景

配置的复用发生在 `env/presets.py`，加载后仍然是普通 `SceneCfg`。后端只接收展开后的配置，不认识 Franka、ManipTrans 或算法名称。

| 目录 | 负责什么 |
|---|---|
| `configs/robots/{arm,hand,humanoid}` | 模型路径、导入选项、初始关节、驱动和求解参数；不含摆放、材质或灯光 |
| `assets/materials` | 铝、塑料、橡胶、带粗糙度图的金属等可复用视觉材质 |
| `configs/lighting` | HDR 摄影棚或方向光/环境光组合 |
| `configs/rendering` | 实时或路径追踪的渲染参数 |
| `configs/scenes` | 桌面布局、物体、接触传感器、相机与外观组合，不绑定机器人 |
| `configs/assets` | 可直接运行的组合示例；引用场景和机器人，设置摆放与导入验证条件 |

原始 URDF、USD、网格及纹理仍在 `assets/`，不改写源资产。已有内联 YAML 继续有效。

## 引用与覆盖

任意配置映射可以写 `ref: 相对文件.yaml`，引用文件的顶层必须也是映射。`ref` 同级字段覆盖预设：字典逐层合并，列表、标量、`null` 整体替换。没有额外注册、环境变量或搜索目录。

例如，在模块内新建 `configs/assets/my_scene.yaml`：

```yaml
ref: ../scenes/tabletop_hdr.yaml
renderer:
  ref: ../rendering/realtime.yaml
assets:
  robot:
    ref: ../robots/arm/ur5.yaml
    position: [-0.35, 0, 0.75]
    fixed_base: true
    gravity: false
  cube:
    visual_material:
      ref: ../../assets/materials/aluminum.yaml
      roughness: 0.35
  sphere:
    visual_material:
      ref: ../../assets/materials/rubber.yaml
```

这里复用了摄影棚与桌面，只选择 UR5、铝方块和橡胶外观的球。没有复制 Franka 的关节或灯光定义。`fixed_base: true`、`gravity: false` 是资产检查条件，项目任务应按自己的物理需求设置。

```bash
python docker/run.py run -- --config configs/assets/my_scene.yaml \
  --steps 60 --rendering-mode quality --screenshot outputs/my_scene.png
```

重要规则：

- **路径相对于写下它的 YAML**。机器人文件里的 `source`、材质里的纹理、灯光里的 HDR，都按各自文件解析；在场景里覆盖路径时，按场景文件解析。与启动目录无关。
- **显式新 `ref` 替换该节点原先的预设**，随后应用同级覆盖。因此换机器人不会残留上一台的关节，换材质不会意外保留旧纹理。不写新 `ref` 时，例如 `drives: {all: {stiffness: 50}}`，只覆盖刚度并保留已有阻尼。
- `visual_material: null` 恢复源资产材质。`{}` 表示不覆盖已有字典，不能用于删除继承的实体；实体集合不同的场景应组合自己的基础布局。
- 视觉材质仅改变外观，不改变质量、摩擦、碰撞。当前覆盖粒度是整个实体；机器人不设置该字段时保留源模型的分部件材质。按连杆选择材质尚未提供。
- 引用缺失、循环引用、配置字段拼错会报错，不静默回退。

## 放进宿主项目后

整个 `isaacLabEnvs/` 复制到项目根目录后，可在项目的 `configs/scene.yaml` 中直接引用模块：

```yaml
ref: ../isaacLabEnvs/configs/scenes/tabletop_hdr.yaml
cache: ../.cache/sim
renderer:
  ref: ../isaacLabEnvs/configs/rendering/realtime.yaml
assets:
  robot:
    ref: ../isaacLabEnvs/configs/robots/arm/franka.yaml
    position: [-0.35, 0, 0.75]
    fixed_base: true
    gravity: false
```

在宿主项目根目录运行：

```bash
python isaacLabEnvs/docker/run.py run --project . -- \
  --config configs/scene.yaml --steps 60 --screenshot outputs/scene.png
```

项目自己的机器人、材质也用相同格式定义和引用。更换这些配置不需要重建 Docker；只有运行依赖变化才需要重新构建镜像。任务、数据集、算法继续留在宿主项目。

## 录制与迁移

`save_scene()` 和 `--record` 生成的 `.scene.yaml` 保存**已展开的有效参数**，不保存 `ref`。后续修改材质库不会改变旧录制的参数。URDF、网格、纹理仍是相对路径引用，不会打包进 YAML；迁移时需保留相同相对目录和对应资产版本。已有录制回放命令不变。
