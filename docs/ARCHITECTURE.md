# ARCHITECTURE

本文档描述桌面字幕软件的目标架构，用于指导当前进行中的上帝类拆分和后续重构。

当前项目的目标不是实现教科书式的完整 Clean Architecture，而是在不过度设计的前提下，得到一套足够干净、可维护、可扩展的工程结构：

- 核心业务围绕 FunASR 语音识别展开
- 产品形态是面向普通用户的 Windows 桌面字幕软件
- 默认开箱即用，不走 geek 风格的复杂自定义拼装
- 当前仅支持 Windows
- 展示层需要为未来跨平台预留接口
- 样式系统需要支持后续快速增加字幕预设

## 设计原则

### 1. 优先服务产品目标，而不是为分层而分层

该项目的核心能力很明确：

- 读取麦克风音频
- 使用 FunASR 做实时或非实时识别
- 将字幕渲染到桌面
- 提供用户友好的预设样式

因此架构设计应优先围绕这条主链路展开，而不是引入大量仅为满足理论分层的中间层。

### 2. 只隔离真正会变化的部分

当前最容易变化的部分是：

- 识别模式实现
- 展示实现
- 字幕样式预设
- 配置结构和设置页

当前相对稳定的部分是：

- 应用启动和生命周期
- 字幕展示数据模型
- 文本后处理基础能力

### 3. 保持几条硬边界

- `recognition` 不直接操作 Qt 窗口
- `presentation` 不依赖 FunASR 的 API 细节
- `app` 只做装配和生命周期，不堆业务分支
- 样式定义与具体展示实现解耦

## 目标目录结构

```text
src/
  main.py

  subtitle_app/
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

说明：

- `subtitle_app` 是新的顶层包名建议，用于表达“字幕产品应用”，避免继续沿用当前混合了实现与产品边界的命名。
- 若重构初期不希望立即改包名，也可以先沿用 `desktop_subtitle`，待结构稳定后再统一迁移。

## 分层说明

### app

职责：

- 程序启动入口后的应用装配
- 生命周期管理
- 将识别层、展示层、配置层连接起来

约束：

- 不放字幕算法
- 不放样式绘制逻辑
- 不放识别模式判断细节

建议拆分：

- `bootstrap.py`：创建对象图
- `application.py`：启动、停止、异常处理、退出顺序

### core

`core` 是项目中最稳定的一层，承载不依赖 Qt 和 FunASR 的业务概念。

职责：

- 定义字幕和应用的核心数据结构
- 定义识别模式、样式标识、展示状态等稳定模型
- 放置字幕文本生命周期处理逻辑
- 放置通用文本后处理逻辑

建议内容：

- `models.py`
  - `RecognitionMode`
  - `SubtitleSegment`
  - `SubtitleViewState`
  - `StyleId`
- `settings.py`
  - 面向产品的配置模型
- `subtitle_pipeline.py`
  - 增量字幕合并
  - 自动清屏策略
  - 状态文本与正式字幕的协调
- `text_postprocess.py`
  - 文本提取
  - 文本替换
  - 基础规整逻辑

约束：

- 不依赖 Qt 类型
- 不依赖 FunASR 返回结构之外的实现细节
- 不直接读写配置文件

### recognition

职责：

- 从麦克风采集音频
- 调用 FunASR 执行识别
- 以统一格式输出识别结果和状态

该层允许直接依赖 FunASR 和音频库，不需要为了理论纯度再额外包多层接口。

推荐结构：

- `audio_source.py`
  - 麦克风输入
  - 音频缓冲
  - 队列溢出处理
- `engine.py`
  - 识别引擎门面
  - 根据模式选择具体 session
- `realtime_session.py`
  - 实时识别流程
- `offline_session.py`
  - 非实时识别流程

后续如确有必要再加入：

- `hybrid_session.py`

但当前产品需求只有“实时”和“非实时”，因此目标架构中先不把混合模式作为主结构的一部分。

输出形式建议统一为事件或回调：

- `on_partial(text)`
- `on_final(text)`
- `on_status(text)`
- `on_error(message)`

关键约束：

- 不直接更新 UI
- 不直接保存配置
- 不依赖 Qt Widget

### presentation

职责：

- 持有展示状态
- 管理字幕样式
- 将通用展示模型交给具体平台实现进行渲染

这是未来跨平台预留空间的关键层。

#### presentation/model.py

这里定义展示层的通用模型，不依赖 Qt。

建议示例：

```python
from dataclasses import dataclass


@dataclass
class SubtitleViewState:
    subtitle_text: str
    status_text: str
    style_id: str
    visible: bool
    animation_progress: float


@dataclass
class SubtitleStyleSpec:
    font_family: str
    font_size: int
    text_color: str
    background_kind: str
    padding: int
    max_lines: int
    align: str
```

这里的价值在于：

- 识别层不关心 Qt
- 样式系统不直接绑定 QWidget
- 将来做别的平台时，尽量复用同一套展示模型

#### presentation/controller.py

职责：

- 接收识别结果
- 调用 `core.subtitle_pipeline`
- 维护当前 `SubtitleViewState`
- 驱动具体展示实现更新

它是展示层的协调器，不负责具体绘制。

#### presentation/styles

职责：

- 管理字幕样式预设
- 定义样式接口
- 提供样式注册表

建议接口保持轻量：

```python
class SubtitleStyle:
    style_id: str
    display_name: str

    def build_spec(self) -> SubtitleStyleSpec:
        ...
```

样式系统的目标是：

- 快速新增预设
- 统一管理默认字体、颜色、边距、对齐、最大行数等外观参数
- 避免用户手工拼大量参数

如果未来某些样式确实需要完全不同的绘制效果，再进一步增加 renderer 抽象；当前先不做过重设计。

#### presentation/qt

职责：

- Qt 平台下的具体窗口实现
- 托盘交互
- 设置页
- 将 `SubtitleViewState + SubtitleStyleSpec` 渲染到窗口

建议文件：

- `overlay_window.py`
  - 字幕窗口
  - 编辑模式交互
  - 基础动画
- `tray_controller.py`
  - 托盘图标与菜单
- `settings_window.py`
  - 设置页

关键约束：

- Qt 层只消费通用展示模型
- Qt 层不直接感知 FunASR 模型细节
- Qt 层不保存识别策略状态机

## 关键数据流

目标数据流如下：

```text
Microphone
  -> recognition.audio_source
  -> recognition.engine
  -> realtime/offline session
  -> presentation.controller
  -> presentation.styles
  -> presentation.qt.overlay_window
```

解释：

1. 麦克风采集进入 `audio_source`
2. 音频块交给 `engine`
3. `engine` 根据模式分发给实时或非实时 session
4. session 输出字幕事件
5. `presentation.controller` 将识别结果转为展示状态
6. 样式系统提供样式规范
7. Qt 窗口根据状态和样式进行实际绘制

## 配置设计取舍

当前产品方向强调“开箱即用”，因此配置应分成两层：

### 面向用户的产品设置

- 识别模式：实时 / 非实时
- 字幕样式：预设样式 ID
- 麦克风设备
- 是否置顶
- 是否开机启动
- 是否启动到托盘

### 内部高级参数

- `energy_threshold`
- `silence_ms`
- `partial_interval_ms`
- `chunk_size`
- `encoder_chunk_look_back`
- `decoder_chunk_look_back`

原则：

- 普通用户默认只接触第一层
- 第二层允许保留在配置文件中，但不作为产品主界面的核心交互

## 样式系统设计目标

样式系统要服务“预设样式产品化”，而不是“高级用户自己拼装 UI”。

目标：

- 用户只选择样式，而不是手工配置几十个参数
- 新增样式时，只需要新增一个样式实现并注册
- 样式定义尽可能复用统一的展示模型

非目标：

- 不做通用可视化编辑器
- 不做高度自由的布局系统
- 不做 CSS 风格 DSL

## 需要避免的反模式

- `app.py` 继续膨胀为新的上帝类
- `overlay.py` 同时承担窗口、绘制、动画、交互、状态同步全部职责
- `asr.py` 中继续堆积所有模式和状态机
- 展示层直接读取 FunASR 原始输出
- 样式预设直接操作配置文件或 QWidget 内部状态

## 重构落地顺序

建议按以下顺序推进，避免一次性大重写：

1. 先稳定目标模型
   - `core.models`
   - `presentation.model`
   - `core.settings`

2. 拆识别层
   - 从现有 `asr.py` 抽出 `realtime_session.py`
   - 抽出 `offline_session.py`
   - 增加 `engine.py`

3. 拆展示层
   - 将 `overlay.py` 拆成通用展示模型与 Qt 实现
   - 引入样式基类和注册表

4. 收缩装配层
   - 将 `app.py` 收缩到 `bootstrap.py + application.py`

5. 最后再统一整理配置和目录命名

## 一句话原则

本项目的目标架构不是“层数越多越好”，而是：

以 FunASR 识别为核心，以通用展示模型为桥梁，让识别逻辑与平台展示实现解耦，同时为后续样式预设扩展和展示层跨平台预留清晰边界。


