# ARCHITECTURE

本文档面向开发维护人员，记录当前模块划分、依赖边界和运行流程。

## 目标

- 避免上帝类和上帝文件
- 维持单向依赖和清晰职责
- 保持 UI、ASR、配置互相解耦，便于增量迭代和测试

## 模块结构

```text
src/
  main.py                         # 启动入口（仅调用 app.main）
  desktop_subtitle/
    app.py                        # 应用编排（装配依赖、生命周期管理）
    constants.py                  # 默认配置和持久化 key 常量
    config.py                     # 配置读写、参数解析、配置校验
    text_utils.py                 # 文本提取与增量合并等纯逻辑
    audio.py                      # 音频输入回调与队列写入
    asr.py                        # ASRWorker（流式/离线识别循环）
    signals.py                    # Qt 跨模块信号定义
    ui/
      overlay.py                  # 字幕覆盖层绘制和交互
      control_panel.py            # 设置面板 UI 与用户操作
      tray.py                     # 托盘图标和菜单控制
```

## 依赖方向

- `main.py -> app.py`
- `app.py -> config/asr/audio/ui/signals`
- `asr.py -> text_utils/signals`
- `ui/* -> config(仅保存设置接口)`  
- `config.py` 不依赖 `ui/*`、`asr.py`

约束：

- `app.py` 只做装配，不放业务算法。
- `asr.py` 不直接操作 UI 对象，只通过信号输出状态和字幕。
- `ui/*` 不加载模型，不管理音频线程。
- 纯函数优先放入 `text_utils.py` 或 `config.py`，便于单测。

## 运行流程

1. `main.py` 调用 `desktop_subtitle.app.main()`
2. `config.parse_args()` 合并默认值、YAML、CLI 参数
3. 创建 `QApplication`、`SubtitleOverlay`、`OverlayControlPanel`、`TrayController`
4. 创建 `AppSignals`、音频队列和 `ASRWorker`
5. 启动音频流：`audio.build_audio_callback()` 持续向队列写入音频块
6. `ASRWorker` 从队列取数据识别，发出 `subtitle/status/error` 信号
7. UI 响应信号更新字幕或状态
8. 退出时停止音频流、设置 stop_event、回收线程和托盘资源

## 关键数据流

- 音频流：`InputStream -> queue[np.ndarray] -> ASRWorker`
- 字幕流：`ASRWorker -> AppSignals.subtitle -> SubtitleOverlay.set_subtitle`
- 状态流：`ASRWorker/App -> AppSignals.status/error -> Overlay/日志`
- 设置流：`Overlay runtime settings -> config.write_overlay_settings_to_config`

## 改动原则

- 新功能先判断归属模块，再落代码，禁止在 `app.py` 堆业务实现。
- UI 相关只改 `ui/`；识别策略只改 `asr.py`；配置规范只改 `config.py/constants.py`。
- 跨模块复用逻辑优先抽成纯函数，避免在 QWidget 子类中膨胀。
- 变更后至少执行 `python -m compileall src` 做语法和导入校验。

## 后续可继续拆分点

- `ui/overlay.py` 仍较大，可继续拆为：
  - 绘制器（文字/背景/辅助线）
  - 交互控制器（命中检测、拖拽、缩放）
  - 动画控制器（字幕渐显）
- `asr.py` 可按策略拆分为 streaming/offline 两个处理器类。
