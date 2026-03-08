# 桌面实时字幕软件（FunASR）

基于 FunASR 的桌面实时字幕工具，支持流式识别、透明背景叠加字幕、托盘控制与可视化调参。

## 功能

### 1) 实时采集
- 麦克风实时采集（`sounddevice.InputStream`）
- 队列缓冲与溢出保护（满队列丢旧帧，保留最新音频）

### 2) 实时识别
- 流式识别（默认 `paraformer-zh-streaming`）
- 离线分段识别（非 streaming 模型）
- 支持能量阈值、静音分段、最大分段时长、增量字幕合并

### 3) 字幕显示
- 桌面无边框字幕窗（可置顶、可拖动）
- 支持透明 PNG 背景渲染
- 文本框位置/尺寸可编辑，支持渐显动画与自动清屏

### 4) 交互控制
- 系统托盘菜单：显示/隐藏字幕、打开设置、保存设置、退出
- `F2` 进入编辑模式（移动/缩放文本框、拖拽背景偏移）
- `Esc`/关闭窗口：启用托盘时隐藏到托盘，否则退出
- 设置面板支持模型组合切换、模型下载、保存到配置（重启后生效）

### 5) 配置管理
- 配置文件读取与类型校验（YAML）
- 命令行参数覆盖配置文件
- 运行时窗口布局可保存回 `config/app.yaml`
- 首次启动可交互选择模型组合（实时/非实时）

## 一键启动（推荐）

直接双击根目录的 [start.bat](C:/Users/littlebai/workspace/personal/anan_subtitle/start.bat)。

脚本会自动完成：
1. 创建 `.venv`（若不存在）
2. 安装依赖
3. 读取 `config/app.yaml`
4. 启动程序

## 手动启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/main.py --config config\app.yaml
```

示例（命令行覆盖配置）：

```powershell
python src/main.py --config config\app.yaml --font-size 36 --x 100 --y 100
```

## 配置说明

默认配置文件：[config/app.yaml](C:/Users/littlebai/workspace/personal/anan_subtitle/config/app.yaml)  
模板文件：[config/default.yaml](C:/Users/littlebai/workspace/personal/anan_subtitle/config/default.yaml)

常用配置组：
- 窗口：`x`, `y`, `width`, `height`, `lock_size_to_bg`, `windowed_mode`, `stay_on_top`, `opacity`
- 字幕：`font_family`, `font_size`, `text_color`, `text_*`, `text_anim_*`, `subtitle_clear_ms`
- 背景：`bg_image`, `bg_width`, `bg_height`, `bg_offset_x`, `bg_offset_y`
- 运行：`show_control_panel`, `tray_icon_enable`
- 音频：`device`, `samplerate`, `block_ms`, `queue_size`
- 识别：`energy_threshold`, `silence_ms`, `partial_interval_ms`, `max_segment_seconds`
- 流式：`chunk_size`, `encoder_chunk_look_back`, `decoder_chunk_look_back`
- 模型：`model_profile`, `model_download_on_startup`, `model`, `vad_model`, `punc_model`, `disable_vad_model`, `disable_punc_model`

模型组合建议：
- `model_profile: realtime`：低延迟实时字幕
- `model_profile: offline`：非实时模型，准确率优先
- `model_profile: hybrid`：实时模型检测起句 + 非实时模型整句识别
- `model_profile: custom`：手工指定 `model/vad_model/punc_model`

首次运行会提示选择模型组合，并写回 `config/app.yaml`。  
如需提前下载模型，可设置 `model_download_on_startup: true`。

## 常用命令

查看麦克风设备：

```powershell
python -m sounddevice
```

导出默认配置模板：

```powershell
python src/main.py --dump-default-config config\default.yaml
```

试用非实时模型并观察延迟（示例）：

```powershell
python src/main.py --config config\app.yaml --model paraformer-zh
```

直接按组合切换（推荐）：

```powershell
python src/main.py --config config\app.yaml --model-profile offline
```

混合模式（流式检测起句 + 离线整句识别）：

```powershell
python src/main.py --config config\app.yaml --model-profile hybrid
```

运行后可在日志中查看离线模式延迟打点：
- `Offline latency (partial/interval)`：分段内增量字幕延迟
- `Offline latency (final/silence|max-segment-seconds)`：句子最终结果延迟
- 指标说明：`lag`（超出音频时长的额外等待）、`tail`（最近音频到输出的等待）、`infer`（推理耗时）
- `Offline latency summary`：每 5 句输出平均值和 `p95_tail`

## 备注

- 首次运行会下载模型，耗时较长。
- 流式识别调用方式为 `cache + chunk_size + is_final`。

## 许可证

本项目源码采用 [MIT License](C:/Users/littlebai/workspace/personal/anan_subtitle/LICENSE)。

## 第三方开源依赖

本项目当前直接依赖并引用了这些主要开源库：

- `PySide6`：`LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`
- `sounddevice`：`MIT`
- `numpy`：`BSD-3-Clause`
- `funasr`：当前安装包元数据显示 `MIT`，但 classifier 同时出现 `Apache Software License`，发布前建议继续以其上游仓库声明为准核对一次
- `modelscope`：`Apache-2.0`
- `torch`：`BSD-3-Clause`
- `torchaudio`：`BSD` / `BSD-3-Clause` 风格许可证
- `PyYAML`：`MIT`

当前仓库中的自有代码没有复制这些第三方库源码，只是通过正常依赖和 API 调用来使用它们；按当前代码形态，没有看到明显的源码许可证冲突。

但有两点需要单独注意：

- `PySide6` 不是 MIT。你的项目源码可以继续采用 MIT，但如果你后续分发 Windows 二进制或打包版，需要额外遵守 `PySide6/Qt` 的 `LGPL` 要求；按当前发布约束，后续打包应采用动态链接方式，并随发布包附带 `LGPL` 声明和相关许可文本。
- `FunASR` / `ModelScope` 下载的模型权重、模型卡和相关资源，可能有独立于 Python 包本身的使用条款。发布可执行版本前，建议逐个确认你实际分发或自动下载的模型许可，并在 README 或发布说明中注明实际使用模型的来源。

## 开发文档

- 目标架构：[docs/ARCHITECTURE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)
- 当前实现：[docs/CURRENT_ARCHITECTURE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/CURRENT_ARCHITECTURE.md)
- 重构映射：[docs/REFACTOR_MAPPING.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/REFACTOR_MAPPING.md)
- 发布说明：[docs/RELEASE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/RELEASE.md)
