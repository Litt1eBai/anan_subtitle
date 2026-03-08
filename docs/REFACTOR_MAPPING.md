# REFACTOR MAPPING

本文档记录这轮重构从旧结构迁移到目标架构的结果，并保留当前目录与目标设计之间的对应关系。

配套目标设计请参考 [ARCHITECTURE.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)。

## 当前目录

```text
src/
  main.py
  core/
    models.py
    settings.py
    text_postprocess.py
    subtitle_pipeline.py
  app/
    __init__.py
    bootstrap.py
    application.py
  recognition/
    audio_source.py
    engine.py
    engine_config.py
    engine_runtime.py
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
      overlay_window_setup.py
      overlay_window_shell.py
      overlay_window_events.py
      overlay_interaction.py
      overlay_renderer.py
      overlay_window_behavior.py
      overlay_geometry.py
      settings_window.py
      settings_window_models.py
      settings_window_actions.py
      tray_controller.py
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

## 当前状态

本轮重构已完成以下迁移：

- `app.py -> app/bootstrap.py + app/application.py`
- `asr.py -> recognition/engine.py`
- `audio.py -> recognition/audio_source.py`
- `constants.py -> core/models.py + core/settings.py`
- `text_utils.py -> core/text_postprocess.py + core/subtitle_pipeline.py`
- `ui/overlay.py -> presentation/qt/overlay_window.py`
- `ui/control_panel.py -> presentation/qt/settings_window.py`
- `ui/tray.py -> presentation/qt/tray_controller.py`
- 展示样式骨架已落位到 `presentation/styles/*`

兼容入口与旧 `ui/*` 已删除，真实代码现在直接依赖目标目录下的模块。

## 仍待继续收口的点

- `recognition/engine.py` 已抽出运行参数归一化、转写调用和离线延迟统计辅助，但仍承担较多线程与模式协调逻辑
- `presentation/qt/overlay_window.py` 仍承担较多剩余窗口状态和 Qt 事件逻辑
- `presentation/qt/settings_window.py` 已抽出模型组合、下载执行和配置保存辅助，但仍承担较多表单装配和配置回填逻辑

## 当前文件到目标文件速查表

| 当前文件 | 主要目标文件 | 说明 |
| --- | --- | --- |
| `src/main.py` | `src/main.py` | 保持薄入口 |
| `src/app/__init__.py` | `src/app/application.py` | 包入口导出 `main` |
| `src/app/bootstrap.py` | `src/app/bootstrap.py` | 对象装配 |
| `src/app/application.py` | `src/app/application.py` | 生命周期与退出控制 |
| `src/recognition/audio_source.py` | `src/recognition/audio_source.py` | 音频输入与缓冲 |
| `src/recognition/engine.py` | `src/recognition/engine.py` | 识别门面与线程协调 |
| `src/recognition/engine_config.py` | `src/recognition/engine.py` 周边辅助 | worker 运行参数与离线模型参数辅助 |
| `src/recognition/engine_runtime.py` | `src/recognition/engine.py` 周边辅助 | 转写调用、字幕输出与离线延迟统计辅助 |
| `src/recognition/realtime_session.py` | `src/recognition/realtime_session.py` | 实时识别流程 |
| `src/recognition/offline_session.py` | `src/recognition/offline_session.py` | 非实时识别流程 |
| `src/core/models.py` | `src/core/models.py` | 模式与稳定标识 |
| `src/core/settings.py` | `src/core/settings.py` | 默认设置与配置逻辑 |
| `src/core/text_postprocess.py` | `src/core/text_postprocess.py` | 文本提取与后处理 |
| `src/core/subtitle_pipeline.py` | `src/core/subtitle_pipeline.py` | 增量文本合并 |
| `src/presentation/model.py` | `src/presentation/model.py` | 通用展示模型、动画状态与设置归一化 |
| `src/presentation/controller.py` | `src/presentation/controller.py` | 展示状态与识别事件协调 |
| `src/presentation/styles/base.py` | `src/presentation/styles/base.py` | 样式接口 |
| `src/presentation/styles/registry.py` | `src/presentation/styles/registry.py` | 样式注册表 |
| `src/presentation/styles/preset_default.py` | `src/presentation/styles/preset_default.py` | 默认样式预设 |
| `src/presentation/qt/overlay_window.py` | `src/presentation/qt/overlay_window.py` | Qt 字幕窗口 |
| `src/presentation/qt/overlay_window_setup.py` | `src/presentation/qt/overlay_window.py` 周边辅助 | 初始化参数解释与样式/运行时构造辅助 |
| `src/presentation/qt/overlay_window_shell.py` | `src/presentation/qt/overlay_window.py` 周边辅助 | 窗口 flags 刷新与壳层更新辅助 |
| `src/presentation/qt/overlay_window_events.py` | `src/presentation/qt/overlay_window.py` 周边辅助 | 键盘/关闭/拖拽释放事件辅助 |
| `src/presentation/qt/overlay_interaction.py` | `src/presentation/qt/overlay_window.py` 周边辅助 | 交互几何与拖拽状态辅助 |
| `src/presentation/qt/overlay_renderer.py` | `src/presentation/qt/overlay_window.py` 周边辅助 | 绘制与文本排版辅助 |
| `src/presentation/qt/overlay_window_behavior.py` | `src/presentation/qt/overlay_window.py` 周边辅助 | 窗口 flags 与关闭动作辅助 |
| `src/presentation/qt/overlay_geometry.py` | `src/presentation/qt/overlay_window.py` 周边辅助 | 背景/文本矩形与运行时快照辅助 |
| `src/presentation/qt/settings_window.py` | `src/presentation/qt/settings_window.py` | 设置页 |
| `src/presentation/qt/settings_window_models.py` | `src/presentation/qt/settings_window.py` 周边辅助 | 模型组合状态、摘要、下载请求与配置更新辅助 |
| `src/presentation/qt/settings_window_actions.py` | `src/presentation/qt/settings_window.py` 周边辅助 | 下载执行与配置保存辅助 |
| `src/presentation/qt/tray_controller.py` | `src/presentation/qt/tray_controller.py` | 托盘控制 |

## 一句话结论

主结构迁移、配置入口收口和顶层信号桥下沉已经完成，当前重构进入“局部继续收口复杂模块”的阶段。
