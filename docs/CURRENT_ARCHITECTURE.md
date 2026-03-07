# CURRENT ARCHITECTURE

本文档记录当前代码库的真实实现结构，用于帮助开发时理解现状、定位代码和评估重构影响。

如果你想看重构目标，请查看 [ARCHITECTURE.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)。
如果你想看迁移路径，请查看 [REFACTOR_MAPPING.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/REFACTOR_MAPPING.md)。

## 当前定位

当前项目已经完成主要结构迁移，代码收敛到文档定义的目标目录，旧兼容入口已移除。

当前实现可以概括为：

- `app/bootstrap.py` 负责对象装配、首次模型选择和启动准备
- `app/application.py` 负责应用生命周期与运行主循环
- `core/models.py` 负责稳定模式标识
- `core/settings.py` 负责默认配置、模型预设、CLI 参数解析、YAML 读写和配置归一化
- `core/text_postprocess.py` 和 `core/subtitle_pipeline.py` 负责文本提取、后处理与增量合并
- `recognition/` 负责音频输入、识别线程门面和实时/非实时识别 session
- `presentation/model.py` 负责通用展示状态模型、动画状态更新与运行时设置归一化
- `presentation/controller.py` 负责识别事件到展示状态的收口
- `presentation/styles/` 提供默认样式预设和样式注册表
- `presentation/qt/` 负责 Qt 窗口、绘制、交互、设置面板和托盘实现
- `app/bootstrap.py` 内部定义 Qt 信号桥 `AppSignals`

## 当前模块结构

```text
src/
  main.py                         # 启动入口（仅调用 app.main）
  core/
    models.py                     # 稳定模式标识
    settings.py                   # 默认配置、模型预设与配置逻辑
    text_postprocess.py           # 文本提取与后处理
    subtitle_pipeline.py          # 增量字幕拼接
  app/
    __init__.py                   # 包入口，导出 main
    bootstrap.py                  # 对象装配与启动准备
    application.py                # 生命周期与事件循环
  recognition/
    audio_source.py               # 音频输入回调与队列写入
    engine.py                     # ASRWorker 门面与模式分发
    realtime_session.py           # 实时识别流程
    offline_session.py            # 非实时识别流程
  presentation/
    model.py                      # 通用展示状态模型
    controller.py                 # 展示状态协调器
    styles/
      base.py                     # 样式接口定义
      registry.py                 # 样式注册表
      preset_default.py           # 默认样式预设
    qt/
      overlay_window.py           # Qt 字幕窗口实现
      overlay_interaction.py      # 编辑几何与拖拽状态辅助
      overlay_renderer.py         # 绘制辅助`r`n      overlay_window_behavior.py  # 窗口 flags 与关闭动作辅助
      settings_window.py          # 设置面板 UI（含模型组合切换/下载）
      tray_controller.py          # 托盘图标和菜单控制
```

## 当前依赖方向

- `main.py -> app.application`
- `app/application.py -> app/bootstrap.py -> core/recognition/presentation`
- `recognition/* -> core/* -> signals`
- `presentation/controller.py -> presentation.model -> presentation/qt/*`
- `core/settings.py` 不依赖 `presentation/qt/*`、`recognition/*`

## 当前运行流程

1. `main.py` 调用 `app.main()`，包入口再转到 `app/application.py`
2. `core.settings.parse_args()` 合并默认值、YAML、CLI 参数
3. 首次运行提示用户选择模型组合，并写回 `config/app.yaml`
4. 根据配置可选预下载模型组合
5. `app/bootstrap.py` 创建 `QApplication`、`SubtitleOverlay`、`OverlayControlPanel`、`TrayController`
6. 创建 `AppSignals`、音频队列和 `recognition.engine.ASRWorker`
7. `recognition.audio_source.build_audio_callback()` 持续向队列写入音频块
8. `ASRWorker` 从队列取数据识别，发出 `subtitle/status/error` 信号
9. `presentation/controller.py` 接收识别信号并生成展示状态
10. `presentation/qt/overlay_window.py` 根据展示状态更新字幕或状态
11. 退出时停止音频流、停止线程并回收托盘资源

## 当前主要问题

### 1. `recognition/engine.py` 仍是识别相关的核心协调点

虽然实时和非实时流程已经拆到独立 session，但当前 `engine.py` 仍承担：

- 模型加载与 worker 门面
- 模式选择
- 通用线程生命周期
- 会话切换与共享状态协调

### 2. `presentation/qt/overlay_window.py` 仍偏重

当前 `overlay_window.py` 仍同时承担：

- QWidget 窗口行为
- 剩余展示状态应用
- 编辑模式交互
- 窗口显隐事件

## 当前仍然有效的约束

- `recognition/*` 不直接操作 UI 对象，只通过信号输出状态和字幕
- `presentation/controller.py` 负责识别事件到展示状态的收口
- `presentation/styles/` 承担样式预设定义
- Qt 相关绘制和交互只留在 `presentation/qt/*`
- 新逻辑不再进入已移除的兼容入口层

## 当前文档的用途

本文件只描述“现在代码是什么样”。

对应文档：

- 目标架构：[ARCHITECTURE.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)
- 重构映射：[REFACTOR_MAPPING.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/REFACTOR_MAPPING.md)

