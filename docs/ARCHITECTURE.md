# ARCHITECTURE

本文档描述项目的目标架构，也就是后续功能开发默认遵循的结构边界。

项目目标不是实现教科书式的完整 Clean Architecture，而是在不过度设计的前提下，得到一套足够干净、可维护、可扩展的工程结构：

- 核心业务围绕 FunASR 语音识别展开
- 产品形态是面向普通用户的 Windows 桌面字幕软件
- 默认开箱即用，不走 geek 风格的复杂自定义拼装
- 当前仅支持 Windows
- 展示层需要为未来跨平台预留接口
- 样式系统需要支持后续快速增加字幕预设

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
    audio_source.py
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
      tray_controller.py
      settings_window.py
```

## 设计原则

### 1. 优先服务产品目标

当前架构只服务几件事：

- 读取麦克风音频
- 使用 FunASR 做实时或非实时识别
- 将字幕渲染到桌面
- 提供用户友好的预设样式

因此架构设计应围绕这条主链路展开，而不是引入过多理论层次。

### 2. 只隔离真正会变化的部分

当前最容易变化的部分：

- 识别模式实现
- 展示实现
- 字幕样式预设
- 配置结构和设置页

当前相对稳定的部分：

- 应用启动和生命周期
- 字幕展示数据模型
- 文本后处理基础能力

### 3. 保持几条硬边界

- `recognition` 不直接操作 Qt 窗口
- `presentation` 不依赖 FunASR 的 API 细节
- `app` 只做装配和生命周期，不堆业务分支
- 样式定义与具体展示实现解耦

## 模块职责

### app

职责：

- 程序装配
- 生命周期管理
- 将识别层、展示层、配置层连接起来

约束：

- 不放字幕算法
- 不放样式绘制逻辑
- 不放识别模式判断细节

### core

职责：

- 定义稳定业务模型
- 管理配置模型与配置读写
- 管理字幕文本生命周期
- 管理文本后处理逻辑

约束：

- 不依赖 Qt
- 不依赖 FunASR 运行时细节

### recognition

职责：

- 从麦克风采集音频
- 调用 FunASR 执行识别
- 统一输出识别结果和状态

约束：

- 不直接更新 UI
- 不直接保存配置

### presentation

职责：

- 持有展示状态
- 管理字幕样式
- 将通用展示模型交给具体平台实现进行渲染

约束：

- 展示模型不依赖 Qt
- Qt 实现只消费通用展示模型

## 关键数据流

```text
Microphone
  -> recognition.audio_source
  -> recognition.engine
  -> realtime/offline session
  -> presentation.controller
  -> presentation.styles
  -> presentation.qt.overlay_window
```

## 样式系统目标

- 用户选择预设，而不是手工调整大量参数
- 新增样式时，只需要新增一个样式实现并注册
- 样式定义尽量复用统一的展示模型

## 需要避免的反模式

- `app` 再次膨胀成上帝类
- `overlay_window.py` 再次回收绘制、动画、交互、状态同步全部职责
- `recognition/engine.py` 重新堆积所有模式和状态机
- 展示层直接读取 FunASR 原始输出
- 样式预设直接操作配置文件或 QWidget 内部状态

## 一句话原则

以 FunASR 识别为核心，以通用展示模型为桥梁，让识别逻辑与平台展示实现解耦，同时为后续样式预设扩展和展示层跨平台预留清晰边界。
