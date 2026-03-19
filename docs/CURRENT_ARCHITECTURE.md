# CURRENT ARCHITECTURE

本文档记录当前代码库的真实实现结构，用于帮助开发时理解现状、定位代码和评估变更影响。

如果你想看文档总入口，请查看 [INDEX.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/INDEX.md)。

如果你想看目标边界，请查看 [ARCHITECTURE.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)。
如果你想看下一阶段工作，请查看 [NEXT_TARGET.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/NEXT_TARGET.md)。

## 当前定位

当前项目已经完成主要结构迁移，代码基本收敛到目标目录。现在的重点不再是大规模搬目录，而是围绕发布和后续功能开发保持结构稳定。

## 当前模块结构

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
    engine_loader.py
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

## 当前职责分布

- `app/bootstrap.py`
  - 对象装配
  - 首次模型选择
  - Qt 信号桥创建
- `app/application.py`
  - 应用生命周期
  - 启停顺序
  - 资源回收
- `core/settings.py`
  - 默认配置
  - YAML 读写
  - CLI 参数解析
  - 配置归一化
- `recognition/*`
  - 音频输入
  - 识别线程
  - 运行参数归一化
  - 模型加载
  - 转写调用
  - 实时/非实时 session
- `presentation/model.py`
  - 通用展示状态
  - 动画状态
  - 运行时设置归一化
- `presentation/controller.py`
  - 识别事件到展示状态的收口
- `presentation/qt/*`
  - Qt 窗口
  - 绘制
  - 交互
  - 设置窗口
  - 托盘

## 当前关键流程

1. `main.py` 调用 `app.main()`
2. `core.settings.parse_args()` 合并默认值、YAML、CLI 参数
3. `bootstrap.py` 创建 Qt 对象、信号、音频队列和 `ASRWorker`
4. `audio_source.py` 持续向队列写入音频块
5. `ASRWorker` 通过：
   - `engine_config.py` 归一化运行参数
   - `engine_loader.py` 加载模型
   - `engine_runtime.py` 执行转写和延迟统计
6. `offline_session.py` 或 `realtime_session.py` 跑识别循环
7. `presentation/controller.py` 将识别事件转成展示状态
8. `presentation/qt/overlay_window.py` 渲染字幕

## 当前状态判断

当前代码库已经进入“可继续稳定开发”的状态：

- 主结构已经稳定
- 展示层已经达到“够干净”的边界
- 识别层已经形成 `engine_config / engine_loader / engine_runtime / engine` 的明确分工
- 测试保护网已经覆盖主要重构边界

## 当前仍然偏重的模块

### `src/recognition/engine.py`

仍承担：

- worker 门面
- 通用线程生命周期
- 会话切换与共享状态协调

### `src/presentation/qt/overlay_window.py`

仍承担：

- QWidget 窗口行为
- 剩余展示状态应用
- 编辑模式交互与少量事件转发
- 窗口显隐事件

### `src/presentation/qt/settings_window.py`

仍承担：

- QWidget 表单和信号连接
- 运行时配置回填与保存
- 部分交互状态切换
- 下载触发和错误提示

## 当前仍然有效的约束

- `recognition/*` 不直接操作 UI 对象
- `presentation/controller.py` 负责识别事件到展示状态的收口
- `presentation/styles/` 承担样式预设定义
- Qt 相关绘制和交互只留在 `presentation/qt/*`

## 一句话结论

当前结构已经足够作为下一阶段功能开发和发布准备的稳定基线。
