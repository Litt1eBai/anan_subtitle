# REFACTOR MAPPING

本文档用于指导从当前代码结构迁移到目标架构。重点不是一次性重写，而是给出清晰、可分阶段执行的文件映射和拆分顺序。

配套目标设计请参考 [ARCHITECTURE.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)。

## 当前目录

```text
src/
  main.py
  desktop_subtitle/
    app.py
    asr.py
    audio.py
    config.py
    constants.py
    signals.py
    text_utils.py
    ui/
      overlay.py
      control_panel.py
      tray.py
```

## 目标目录

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

## 映射原则

- 优先做“拆分”，其次才是“改名”
- 前几轮重构可以保留 `desktop_subtitle` 包名，避免同时改结构和导入路径
- 待职责稳定后，再将包名统一迁移到 `subtitle_app`
- 映射表中的“目标文件”表示主要归属，不代表必须一步到位

## 文件级映射

### 1. 启动与装配

当前文件：

- `src/main.py`
- `src/desktop_subtitle/app.py`

目标文件：

- `src/main.py`
- `src/subtitle_app/app/bootstrap.py`
- `src/subtitle_app/app/application.py`

迁移建议：

- `src/main.py`
  - 保持薄入口
  - 继续只负责调用应用启动函数

- `app.py`
  - 拆出对象装配到 `bootstrap.py`
  - 拆出生命周期控制到 `application.py`
  - 移除识别模式细节、模型下载细节、UI 具体操作细节

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

- `src/desktop_subtitle/asr.py`
- `src/desktop_subtitle/audio.py`

目标文件：

- `src/subtitle_app/recognition/engine.py`
- `src/subtitle_app/recognition/realtime_session.py`
- `src/subtitle_app/recognition/offline_session.py`
- `src/subtitle_app/recognition/audio_source.py`

迁移建议：

- `audio.py -> audio_source.py`
  - 保留音频采集回调和队列溢出保护
  - 不再感知识别模式和字幕逻辑

- `asr.py -> engine.py + realtime_session.py + offline_session.py`
  - `ASRWorker` 不再作为单文件大类继续膨胀
  - 先把实时流程抽出去
  - 再把非实时流程抽出去
  - `engine.py` 只保留模式选择、启动和停止协调

现有 `asr.py` 的建议拆分：

- 放到 `engine.py`
  - 工作线程门面
  - session 创建逻辑
  - 通用启动/停止

- 放到 `realtime_session.py`
  - `_run_streaming`
  - `_transcribe_streaming`
  - streaming cache 管理
  - 增量文本合并调用点

- 放到 `offline_session.py`
  - `_run_offline`
  - `_timed_transcribe`
  - 离线延迟统计

暂缓迁移的部分：

- 当前混合模式逻辑

处理建议：

- 短期可先继续留在 `engine.py`
- 若后续仍保留该模式，再新增 `hybrid_session.py`
- 若产品决定只保留两种模式，则在后续迭代中移除

### 3. 核心模型与文本处理

当前文件：

- `src/desktop_subtitle/text_utils.py`
- `src/desktop_subtitle/constants.py`
- `src/desktop_subtitle/config.py`

目标文件：

- `src/subtitle_app/core/models.py`
- `src/subtitle_app/core/settings.py`
- `src/subtitle_app/core/subtitle_pipeline.py`
- `src/subtitle_app/core/text_postprocess.py`

迁移建议：

- `text_utils.py -> text_postprocess.py + subtitle_pipeline.py`
  - `extract_text` 归入 `text_postprocess.py`
  - `replace_sentence_initial_wo` 归入 `text_postprocess.py`
  - `merge_incremental_text` 归入 `subtitle_pipeline.py`

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

- `src/desktop_subtitle/ui/overlay.py`
- `src/desktop_subtitle/ui/control_panel.py`
- `src/desktop_subtitle/ui/tray.py`
- `src/desktop_subtitle/signals.py`

目标文件：

- `src/subtitle_app/presentation/model.py`
- `src/subtitle_app/presentation/controller.py`
- `src/subtitle_app/presentation/styles/base.py`
- `src/subtitle_app/presentation/styles/registry.py`
- `src/subtitle_app/presentation/styles/preset_default.py`
- `src/subtitle_app/presentation/qt/overlay_window.py`
- `src/subtitle_app/presentation/qt/settings_window.py`
- `src/subtitle_app/presentation/qt/tray_controller.py`

迁移建议：

- `overlay.py`
  - 这是当前最明显的上帝类之一
  - 先拆“展示模型”和“Qt 实现”的边界

建议拆分方向：

- `presentation/model.py`
  - `SubtitleViewState`
  - `SubtitleStyleSpec`
  - 与平台无关的展示数据

- `presentation/controller.py`
  - 接收识别层事件
  - 维护当前展示状态
  - 调用样式系统和具体视图更新

- `presentation/qt/overlay_window.py`
  - 保留 QWidget
  - 保留鼠标交互和窗口交互
  - 不再承担字幕业务状态流转

- `presentation/styles/*`
  - 吸收当前和样式强相关的默认字体、颜色、布局参数
  - 后续作为预设样式扩展点

- `control_panel.py -> settings_window.py`
  - 继续放在 Qt 实现层
  - 不直接维护识别状态机
  - 只负责编辑产品设置和触发保存

- `tray.py -> tray_controller.py`
  - 保持托盘层职责
  - 只负责窗口显隐、设置入口、退出入口

- `signals.py`
  - 如果仍基于 Qt signal，可暂时保留在 `presentation/qt` 附近
  - 如果后续展示控制器变为普通 Python 协调器，则该文件应逐步收缩或消失

### 5. 包名迁移

当前包名：

- `desktop_subtitle`

目标包名：

- `subtitle_app`

建议顺序：

1. 先在现有包名下完成职责拆分
2. 等导入关系稳定后再统一重命名包

原因：

- 同时做职责拆分和全量导入迁移，风险较高
- 当前正处于重构过程中，应优先缩小单次改动面

## 分阶段实施建议

### Phase 1: 结构止血

目标：

- 避免 `app.py`、`asr.py`、`overlay.py` 继续变大

动作：

- 新增目标目录和空模块
- 停止往旧上帝类继续塞新逻辑
- 新代码优先写入目标文件

### Phase 2: 先拆识别

目标：

- 让实时/非实时模式脱离单一大类

动作：

- 从 `asr.py` 抽出 realtime session
- 从 `asr.py` 抽出 offline session
- 用一个薄 `engine.py` 接管模式切换

### Phase 3: 再拆展示

目标：

- 为跨平台展示预留边界

动作：

- 新增 `presentation/model.py`
- 抽出展示状态模型
- `overlay.py` 收缩为 `qt/overlay_window.py`
- 引入 `styles/base.py` 和 `registry.py`

### Phase 4: 收缩 app

目标：

- 应用启动和对象装配清晰化

动作：

- `app.py` 拆成 `bootstrap.py` 与 `application.py`
- 退出顺序、资源释放统一收口

### Phase 5: 包名与配置整理

目标：

- 收尾并提升一致性

动作：

- 将 `desktop_subtitle` 重命名为 `subtitle_app`
- 整理 `config.py/constants.py` 的归属
- 统一文档和入口说明

## 当前文件到目标文件速查表

| 当前文件 | 主要目标文件 | 说明 |
| --- | --- | --- |
| `src/main.py` | `src/main.py` | 保持薄入口 |
| `src/desktop_subtitle/app.py` | `src/subtitle_app/app/bootstrap.py` | 对象装配 |
| `src/desktop_subtitle/app.py` | `src/subtitle_app/app/application.py` | 生命周期与退出控制 |
| `src/desktop_subtitle/asr.py` | `src/subtitle_app/recognition/engine.py` | 线程门面与模式调度 |
| `src/desktop_subtitle/asr.py` | `src/subtitle_app/recognition/realtime_session.py` | 实时模式 |
| `src/desktop_subtitle/asr.py` | `src/subtitle_app/recognition/offline_session.py` | 非实时模式 |
| `src/desktop_subtitle/audio.py` | `src/subtitle_app/recognition/audio_source.py` | 音频输入与缓冲 |
| `src/desktop_subtitle/text_utils.py` | `src/subtitle_app/core/text_postprocess.py` | 文本提取与后处理 |
| `src/desktop_subtitle/text_utils.py` | `src/subtitle_app/core/subtitle_pipeline.py` | 增量文本合并 |
| `src/desktop_subtitle/constants.py` | `src/subtitle_app/core/models.py` | 模式与稳定标识 |
| `src/desktop_subtitle/constants.py` | `src/subtitle_app/core/settings.py` | 默认产品设置 |
| `src/desktop_subtitle/config.py` | `src/subtitle_app/core/settings.py` | 设置模型定义逐步迁移 |
| `src/desktop_subtitle/ui/overlay.py` | `src/subtitle_app/presentation/model.py` | 展示状态模型抽离 |
| `src/desktop_subtitle/ui/overlay.py` | `src/subtitle_app/presentation/qt/overlay_window.py` | Qt 字幕窗口 |
| `src/desktop_subtitle/ui/control_panel.py` | `src/subtitle_app/presentation/qt/settings_window.py` | 设置页 |
| `src/desktop_subtitle/ui/tray.py` | `src/subtitle_app/presentation/qt/tray_controller.py` | 托盘控制 |
| `src/desktop_subtitle/signals.py` | `src/subtitle_app/presentation/controller.py` 或 `src/subtitle_app/presentation/qt/*` | 视最终事件机制而定 |

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

这次重构不追求一步到位，而是以目标目录为收敛方向，先停止上帝类继续膨胀，再按“识别层 -> 展示层 -> 装配层 -> 包名”的顺序持续迁移。

