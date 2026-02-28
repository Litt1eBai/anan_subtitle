# 桌面实时字幕软件（FunASR）

功能：

- 麦克风实时采集
- FunASR 实时识别（默认 `paraformer-zh-streaming`）
- 桌面小窗字幕显示（置顶、可拖动）
- 支持透明 PNG 背景渲染

## 一键启动（推荐）

直接双击根目录的 [start.bat](C:/Users/littlebai/workspace/personal/anan_subtitle/start.bat)。

脚本会自动完成：

1. 创建 `.venv`（若不存在）
2. 安装依赖
3. 读取 `config/app.yaml`
4. 启动程序

## 配置文件（所有参数可配）

默认读取 [config/app.yaml](C:/Users/littlebai/workspace/personal/anan_subtitle/config/app.yaml)。

模板文件是 [config/default.yaml](C:/Users/littlebai/workspace/personal/anan_subtitle/config/default.yaml)。

`app.yaml` 内已经为每个配置项加了注释，可直接修改。

可配置项（全部）：

- `x`, `y`, `width`, `height`, `lock_size_to_bg`, `stay_on_top`
- `opacity`
- `font_family`, `font_size`, `text_color`
- `text_x`, `text_y`, `text_width`, `text_height`, `text_max_lines`
- `text_anim_enable`, `text_anim_duration_ms`, `text_anim_fade_px`, `text_anim_offset_y` (deprecated)
- `subtitle_clear_ms`
- `bg_image`, `bg_width`, `bg_height`, `bg_offset_x`, `bg_offset_y`
- `show_control_panel`, `tray_icon_enable`
- `device`
- `samplerate`, `block_ms`, `queue_size`
- `energy_threshold`, `silence_ms`
- `partial_interval_ms`, `max_segment_seconds`
- `chunk_size`, `encoder_chunk_look_back`, `decoder_chunk_look_back`
- `model`, `vad_model`, `punc_model`
- `disable_vad_model`, `disable_punc_model`

## 手动启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/main.py --config config\app.yaml
```

命令行参数会覆盖配置文件，例如：

```powershell
python src/main.py --config config\app.yaml --font-size 36 --x 100 --y 100
```

## 常用命令

查看麦克风设备：

```powershell
python -m sounddevice
```

导出默认配置模板：

```powershell
python src/main.py --dump-default-config config\default.yaml
```

## 可视化调节

- 启动后默认在系统托盘（Windows 右下角）显示小图标（`tray_icon_enable: true`）。
- 右键托盘图标可进行主要控制：显示字幕、打开设置面板、编辑模式、前台常驻、保存设置、退出。
- `Subtitle Settings` 面板可通过托盘菜单打开，也可通过 `show_control_panel` 控制启动即显示。
- 设置面板支持调整背景图显示大小（`背景宽/背景高`，填 `0` 表示使用原图尺寸）。
- 启用托盘时，按 `Esc` 或关闭窗口会隐藏到托盘，不会直接退出。
- `F2` 可切换编辑模式：
  - 拖拽文本框内区域：移动文本框
  - 拖拽文本框边/角手柄：缩放文本框
  - 拖拽背景图区域：调整背景图片偏移
- 在面板点 `保存到配置` 可将当前位置与尺寸写入 `config/app.yaml`。

## 说明

- 首次运行会下载模型，耗时较长。
- 流式识别调用方式使用 `cache + chunk_size + is_final`。
- 未启用托盘时按 `Esc` 可退出程序；启用托盘时会隐藏到托盘。
