# CURRENT ARCHITECTURE

本文档记录当前代码库的真实实现结构，用于帮助开发时理解现状、定位代码和评估重构影响。

如果你想看重构目标，请查看 [ARCHITECTURE.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)。
如果你想看迁移路径，请查看 [REFACTOR_MAPPING.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/REFACTOR_MAPPING.md)。

## 当前定位

当前项目仍处于上帝类拆分阶段，但已经完成了第一轮目录扁平化：`src/desktop_subtitle/` 已被收敛为 `src/` 下的直接模块和子目录。

当前实现可以概括为：

- `app.py` 负责应用装配、首次模型选择、生命周期管理
- `recognition/` 负责识别线程门面和实时/非实时识别 session
- `audio.py` 负责麦克风音频回调与队列写入
- `config.py/constants.py` 负责配置模型、参数解析和持久化
- `presentation/model.py` 负责通用展示状态模型
- `presentation/controller.py` 负责识别事件到展示状态的收口
- `presentation/qt/overlay_window.py` 负责字幕窗口、绘制、动画和 Qt 事件桥接
- `presentation/qt/overlay_interaction.py` 负责文本框编辑命中与缩放几何逻辑
- `presentation/qt/overlay_renderer.py` 负责字幕文本、动画和编辑辅助线绘制
- `ui/overlay.py`、`ui/overlay_interaction.py`、`ui/overlay_renderer.py` 作为兼容转发层保留旧导入路径
- `ui/control_panel.py` 负责设置面板
- `ui/tray.py` 负责系统托盘

## 当前模块结构

```text
src/
  main.py                         # 启动入口（仅调用 app.main）
  app.py                          # 应用编排（装配依赖、首次模型选择、生命周期管理）
  asr.py                          # 兼容入口，转发到 recognition.engine
  audio.py                        # 音频输入回调与队列写入
  config.py                       # 配置读写、参数解析、配置校验
  constants.py                    # 默认配置和持久化 key 常量
  signals.py                      # Qt 跨模块信号定义
  text_utils.py                   # 文本提取与增量合并等纯逻辑
  recognition/
    engine.py                     # ASRWorker 门面与模式分发
    realtime_session.py           # 实时识别流程
    offline_session.py            # 非实时识别流程
  presentation/
    model.py                      # 通用展示状态模型
    controller.py                 # 展示状态协调器
    qt/
      overlay_window.py           # Qt 字幕窗口实现
      overlay_interaction.py      # 编辑几何辅助
      overlay_renderer.py         # 绘制辅助
  ui/
    overlay.py                    # 兼容转发层
    overlay_interaction.py        # 兼容转发层
    overlay_renderer.py           # 兼容转发层
    control_panel.py              # 设置面板 UI（含模型组合切换/下载）
    tray.py                       # 托盘图标和菜单控制
```

## 当前依赖方向

- `main.py -> app.py`
- `app.py -> config/audio/recognition/presentation/ui/signals`
- `recognition/* -> text_utils/signals`
- `presentation/controller.py -> presentation.model -> presentation/qt/*`
- `ui/* -> presentation/qt/* 或 config(仅保存设置接口)`
- `config.py` 不依赖 `ui/*`、`recognition/*`

## 当前运行流程

1. `main.py` 调用 `app.main()`
2. `config.parse_args()` 合并默认值、YAML、CLI 参数
3. 首次运行提示用户选择模型组合，并写回 `config/app.yaml`
4. 根据配置可选预下载模型组合
5. 创建 `QApplication`、`SubtitleOverlay`、`OverlayControlPanel`、`TrayController`
6. 创建 `AppSignals`、音频队列和 `recognition.engine.ASRWorker`
7. 启动音频流：`audio.build_audio_callback()` 持续向队列写入音频块
8. `ASRWorker` 从队列取数据识别，发出 `subtitle/status/error` 信号
9. `presentation/controller.py` 接收识别信号并生成展示状态
10. `presentation/qt/overlay_window.py` 根据展示状态更新字幕或状态
11. 退出时停止音频流、停止线程并回收托盘资源

## 当前关键数据流

- 音频流：`InputStream -> queue[np.ndarray] -> ASRWorker`
- 字幕流：`ASRWorker -> AppSignals -> SubtitlePresentationController -> SubtitleOverlay.apply_view_state`
- 状态流：`ASRWorker/App -> AppSignals.status/error -> SubtitlePresentationController -> Overlay/日志`
- 设置流：`Overlay runtime settings -> config.write_overlay_settings_to_config`

## 当前主要问题

### 1. `app.py` 仍然承担过多装配外的职责

当前 `app.py` 不只是启动入口，还混入了：

- 首次运行模型选择
- 模型预下载流程
- 部分 UI 初始化细节
- 生命周期控制细节

这使得应用装配和产品逻辑混在一起。

### 2. `recognition/engine.py` 仍是识别相关的核心协调点

虽然实时和非实时流程已经拆到独立 session，但当前 `engine.py` 仍承担：

- 模型加载与 worker 门面
- 模式选择
- 通用线程生命周期
- 会话切换与共享状态协调

它已经比旧 `asr.py` 清晰，但仍是后续继续收缩的重点。

### 3. `presentation/qt/overlay_window.py` 仍偏重

当前 `overlay_window.py` 仍同时承担：

- QWidget 窗口行为
- 剩余展示状态应用
- 编辑模式交互
- 窗口显隐事件

虽然绘制和部分交互几何已经拆出，但它仍未完全收缩成纯视图层。

### 4. 配置模型与产品设置边界仍然混杂

当前配置既包含产品级设置，也包含大量 ASR 内部参数。
对重构而言，这意味着设置页、配置文件和识别逻辑之间仍然耦合较重。

## 当前仍然有效的约束

虽然还在重构中，但以下边界已经基本成立，应继续保持：

- `recognition/*` 不直接操作 UI 对象，只通过信号输出状态和字幕
- `presentation/controller.py` 负责识别事件到展示状态的收口
- Qt 相关绘制和交互优先下沉到 `presentation/qt/*`
- `ui/*` 中的兼容层不再继续承载新逻辑
- 配置读写集中在配置模块，不分散到 UI 细节中

## 当前重构建议

在目标架构完全落地前，当前代码继续演进时应遵守以下规则：

- 不再向 `app.py` 新增识别逻辑
- 不再向 `recognition/engine.py` 新增新模式的大块分支
- 不再向兼容层 `ui/*` 新增任何逻辑
- 新增展示状态优先考虑抽到展示控制器或 Qt 实现层
- 新增绘制和交互辅助优先收敛到 `presentation/qt/*`

## 当前文档的用途

本文件只描述“现在代码是什么样”。

不回答：

- 目标架构最终长什么样
- 文件将如何迁移

对应文档：

- 目标架构：[ARCHITECTURE.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)
- 重构映射：[REFACTOR_MAPPING.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/REFACTOR_MAPPING.md)
