# REFACTOR MAPPING

本文档用于指导从当前代码结构迁移到目标架构。重点不是一次性重写，而是给出清晰、可分阶段执行的文件映射和拆分顺序。

配套目标设计请参考 [ARCHITECTURE.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)。

## 当前目录

```text
src/
  main.py
  asr.py
  audio.py
  config.py
  constants.py
  signals.py
  text_utils.py
  core/
    text_postprocess.py
    subtitle_pipeline.py
  app/
    __init__.py
    bootstrap.py
    application.py
  recognition/
    audio_source.py
    engine.py
    realtime_session.py
    offline_session.py
  presentation/
    model.py
    controller.py
    styles/
      base.py
      registry.py
      preset_default.py
    qt/
      overlay_window.py
      overlay_interaction.py
      overlay_renderer.py
      settings_window.py
      tray_controller.py
  ui/
    overlay.py
    overlay_interaction.py
    overlay_renderer.py
    control_panel.py
    tray.py
```

## 目标目录

```text
src/
  main.py

  app/
    bootstrap.py
    application.py

  core/
    models.py
    settings.py
    subtitle_pipeline.py
    text_postprocess.py

  recognition/
    engine.py
    realtime_session.py
    offline_session.py
    audio_source.py

  presentation/
    model.py
    controller.py
    styles/
      base.py
      registry.py
      preset_default.py
    qt/
      overlay_window.py
      tray_controller.py
      settings_window.py
```

## 映射原则

- 优先做“拆分”，其次才是“改名”
- 当前已完成 `src/desktop_subtitle -> src/` 扁平化，不再引入新的顶层产品包
- 映射表中的“目标文件”表示主要归属，不代表必须一步到位
- 过渡期允许保留兼容入口，例如 `src/asr.py` 和 `src/ui/*`

## 文件级映射

### 1. 启动与装配

当前文件：

- `src/main.py`
- `src/app/__init__.py`
- `src/app/bootstrap.py`
- `src/app/application.py`

目标文件：

- `src/main.py`
- `src/app/bootstrap.py`
- `src/app/application.py`

迁移建议：

- `src/main.py`
  - 保持薄入口
  - 继续只负责调用应用启动函数

- `app/__init__.py` / `app/bootstrap.py` / `app/application.py`
  - 已完成对象装配到 `bootstrap.py` 的第一轮拆分
  - 已完成生命周期控制到 `application.py` 的第一轮拆分
  - 后续继续移除识别模式细节、模型下载细节、UI 具体操作细节

建议归属：

- `bootstrap.py`
  - 创建配置对象
  - 创建识别引擎
  - 创建展示控制器
  - 创建 Qt 窗口和托盘

- `application.py`
  - 负责启动顺序和关闭顺序
  - 负责资源释放
  - 负责全局异常到日志/状态的落地

### 2. 识别层

当前文件：

- `src/asr.py`
- `src/recognition/audio_source.py`
- `src/audio.py`（兼容转发）
- `src/recognition/engine.py`
- `src/recognition/realtime_session.py`
- `src/recognition/offline_session.py`

目标文件：

- `src/recognition/engine.py`
- `src/recognition/realtime_session.py`
- `src/recognition/offline_session.py`
- `src/recognition/audio_source.py`

迁移建议：

- `recognition/audio_source.py`
  - 已承载音频采集回调和队列溢出保护
  - 不再感知识别模式和字幕逻辑

- `audio.py`
  - 仅保留兼容转发，不再承载新逻辑

- `asr.py`
  - 继续只作为兼容入口
  - 不再承载新逻辑

- `recognition/engine.py`
  - 只保留 worker 门面、模式选择、启动和停止协调
  - 继续把具体流程下沉到 session

- `recognition/realtime_session.py`
  - 保持流式识别流程与 streaming cache 管理

- `recognition/offline_session.py`
  - 保持非实时识别流程与延迟统计

暂缓迁移的部分：

- 当前混合模式逻辑

处理建议：

- 短期可继续留在 `recognition/engine.py`
- 若后续仍保留该模式，再新增 `hybrid_session.py`
- 若产品决定只保留两种模式，则在后续迭代中移除

### 3. 核心模型与文本处理

当前文件：

- `src/core/text_postprocess.py`
- `src/core/subtitle_pipeline.py`
- `src/text_utils.py`（兼容转发）
- `src/constants.py`
- `src/config.py`

目标文件：

- `src/core/models.py`
- `src/core/settings.py`
- `src/core/subtitle_pipeline.py`
- `src/core/text_postprocess.py`

迁移建议：

- `core/text_postprocess.py`
  - 已承载 `extract_text` 与 `replace_sentence_initial_wo`

- `core/subtitle_pipeline.py`
  - 已承载 `merge_incremental_text`

- `text_utils.py`
  - 仅保留兼容转发，不再承载新逻辑

- `constants.py`
  - 默认配置与产品设置定义迁移到 `settings.py`
  - 模式常量可迁移到 `models.py`
  - 与展示样式有关的默认值，后续应逐步迁移到 `presentation/styles`

- `config.py`
  - 参数解析与配置文件读写短期可保留
  - 中期将“配置结构定义”逐步迁移到 `core/settings.py`
  - 长期将“加载/保存”拆回 `app` 或单独配置模块

注意：

- 这一轮重构不要求立刻消灭 `config.py`
- 先把“设置模型”和“配置加载实现”区分开即可

### 4. 展示层

当前文件：

- `src/presentation/model.py`
- `src/presentation/controller.py`
- `src/presentation/styles/base.py`
- `src/presentation/styles/registry.py`
- `src/presentation/styles/preset_default.py`
- `src/presentation/qt/overlay_window.py`
- `src/presentation/qt/overlay_interaction.py`
- `src/presentation/qt/overlay_renderer.py`
- `src/presentation/qt/settings_window.py`
- `src/presentation/qt/tray_controller.py`
- `src/ui/overlay.py`
- `src/ui/overlay_interaction.py`
- `src/ui/overlay_renderer.py`
- `src/ui/control_panel.py`（兼容转发）
- `src/ui/tray.py`（兼容转发）
- `src/signals.py`

目标文件：

- `src/presentation/model.py`
- `src/presentation/controller.py`
- `src/presentation/styles/base.py`
- `src/presentation/styles/registry.py`
- `src/presentation/styles/preset_default.py`
- `src/presentation/qt/overlay_window.py`
- `src/presentation/qt/settings_window.py`
- `src/presentation/qt/tray_controller.py`

迁移建议：

- `presentation/model.py`
  - 继续作为平台无关的展示状态模型
  - 后续吸收更多纯展示数据结构

- `presentation/styles/base.py` / `registry.py` / `preset_default.py`
  - 已提供最小样式接口、注册表与默认样式预设
  - 后续新增预设样式优先落到该目录

- `presentation/controller.py`
  - 已经接管识别事件到展示状态的收口
  - 下一步继续把状态应用细节从 Qt 窗口里下沉出来

- `presentation/qt/overlay_window.py`
  - 现已承载 Qt 字幕窗口实现
  - 仍需继续下沉剩余交互和状态应用逻辑

- `presentation/qt/overlay_interaction.py`
  - 已承载文本框编辑命中与缩放几何

- `presentation/qt/overlay_renderer.py`
  - 已承载文本绘制、动画绘制与编辑辅助线绘制

- `presentation/qt/settings_window.py`
  - 已承载设置面板 Qt 实现
  - 继续只负责编辑产品设置和触发保存

- `presentation/qt/tray_controller.py`
  - 已承载托盘 Qt 实现
  - 继续只负责窗口显隐、设置入口、退出入口

- `ui/overlay.py` / `ui/overlay_interaction.py` / `ui/overlay_renderer.py`
  - 仅保留兼容转发，不再继续承载新逻辑

- `ui/control_panel.py` / `ui/tray.py`
  - 仅保留兼容转发，不再继续承载新逻辑

- `signals.py`
  - 如果仍基于 Qt signal，可暂时保留在 Qt 实现附近
  - 如果后续展示控制器变为普通 Python 协调器，则该文件应逐步收缩或消失

## 分阶段实施建议

### Phase 1: 结构止血

目标：

- 避免 `app.py`、`recognition/engine.py`、`ui/overlay.py` 继续变大

动作：

- 新代码优先写入目标目录
- 旧入口只做兼容转发或最小修正

### Phase 2: 收缩识别门面（进行中）

目标：

- 让实时/非实时模式继续脱离中央门面

动作：

- 从 `recognition/engine.py` 继续下沉模式细节
- 新增 `recognition/audio_source.py`
- 把 `audio.py` 收缩为兼容入口或删除

### Phase 3: 拆展示控制与 Qt 实现（进行中）

目标：

- 为跨平台展示预留清晰边界

动作：

- 继续扩展 `presentation/controller.py`
- 抽出展示状态流转
- `ui/overlay.py` 收缩为 `presentation/qt/overlay_window.py`
- 引入 `presentation/styles/base.py` 和 `registry.py`

### Phase 4: 收缩 app（已开始）

目标：

- 应用启动和对象装配清晰化

动作：

- 已完成 `app/bootstrap.py` 与 `app/application.py` 的第一轮拆分
- 继续整理启动准备、资源释放与异常收口

### Phase 5: 配置与入口收尾

目标：

- 收尾并提升一致性

动作：

- 整理 `config.py/constants.py` 的归属
- 删除兼容入口文件
- 统一文档和启动入口说明

## 当前文件到目标文件速查表

| 当前文件 | 主要目标文件 | 说明 |
| --- | --- | --- |
| `src/main.py` | `src/main.py` | 保持薄入口 |
| `src/app/__init__.py` | `src/app/application.py` | 包入口导出 `main` |
| `src/app/bootstrap.py` | `src/app/bootstrap.py` | 对象装配 |
| `src/app/application.py` | `src/app/application.py` | 生命周期与退出控制 |
| `src/asr.py` | `src/recognition/engine.py` | 兼容入口最终收敛到门面 |
| `src/audio.py` | `src/recognition/audio_source.py` | 音频输入与缓冲 |
| `src/text_utils.py` | `src/core/text_postprocess.py` | 文本提取与后处理 |
| `src/text_utils.py` | `src/core/subtitle_pipeline.py` | 增量文本合并 |
| `src/constants.py` | `src/core/models.py` | 模式与稳定标识 |
| `src/constants.py` | `src/core/settings.py` | 默认产品设置 |
| `src/config.py` | `src/core/settings.py` | 设置模型定义逐步迁移 |
| `src/presentation/model.py` | `src/presentation/model.py` | 通用展示模型继续扩充 |
| `src/presentation/controller.py` | `src/presentation/controller.py` | 展示状态与识别事件协调 |
| `src/presentation/qt/overlay_window.py` | `src/presentation/qt/overlay_window.py` | Qt 字幕窗口 |
| `src/presentation/qt/overlay_interaction.py` | `src/presentation/qt/overlay_window.py` 周边辅助 | 交互几何辅助 |
| `src/presentation/qt/overlay_renderer.py` | `src/presentation/qt/overlay_window.py` 周边辅助 | 绘制辅助 |
| `src/ui/control_panel.py` | `src/presentation/qt/settings_window.py` | 设置页 |
| `src/ui/tray.py` | `src/presentation/qt/tray_controller.py` | 托盘控制 |
| `src/signals.py` | `src/presentation/controller.py` 或 `src/presentation/qt/*` | 视最终事件机制而定 |

## 重构时的判断标准

如果一个改动满足以下任一条件，就不应该继续往旧文件里塞：

- 它属于实时/非实时识别流程
- 它属于字幕展示状态而不是 QWidget 细节
- 它属于样式预设定义
- 它属于应用装配和生命周期

如果一个改动满足以下条件，则可以暂时留在旧文件中，等待下一轮搬迁：

- 它只是为保证当前功能不回归而做的小修正
- 它与正在拆出的目标模块高度耦合，暂时切不干净
- 它属于过渡期兼容代码

## 一句话执行策略

这次重构不追求一步到位，而是以目标目录为收敛方向，先停止上帝类继续膨胀，再按“识别层 -> 展示层 -> 装配层 -> 配置与入口”的顺序持续迁移。
