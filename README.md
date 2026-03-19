# 桌面实时字幕软件（FunASR）

基于 FunASR 的 Windows 桌面字幕工具，支持：

- 麦克风实时采集
- 实时 / 非实时识别
- 桌面透明字幕渲染
- 托盘控制与设置面板
- 首次启动模型选择与模型下载

当前代码库已经完成主要重构，适合作为后续功能开发和发布准备的稳定基线。

## 快速开始

推荐直接运行：

```powershell
start.bat
```

手动开发启动：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-lock.txt
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe src\main.py --config config\app.yaml
```

开发前验证：

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall src tests
```

Windows 打包：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build-lock.txt
.\scripts\build_windows.ps1
```

构建完成后，运行：

```powershell
.\dist\anan_subtitle\anan_subtitle.exe
```

## 配置与运行目录

- 源码运行默认配置：[config/app.yaml](C:/Users/littlebai/workspace/personal/anan_subtitle/config/app.yaml)
- 模板配置：[config/default.yaml](C:/Users/littlebai/workspace/personal/anan_subtitle/config/default.yaml)
- 打包版运行态配置默认位置：`%LOCALAPPDATA%\anan_subtitle\config\app.yaml`
- 数据目录 / 日志目录支持三种位置：`app` / `user` / `custom`

首次启动会提示选择模型组合。打包版若勾选立即下载模型，失败时界面会显示错误详情和日志路径。

## 文档索引

完整文档入口见 [docs/INDEX.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/INDEX.md)。

常用文档：

- 架构目标：[docs/ARCHITECTURE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)
- 当前实现：[docs/CURRENT_ARCHITECTURE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/CURRENT_ARCHITECTURE.md)
- 下一阶段：[docs/NEXT_TARGET.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/NEXT_TARGET.md)
- 开发与打包：[docs/DEVELOPMENT_AND_PACKAGING.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/DEVELOPMENT_AND_PACKAGING.md)
- 发布流程：[docs/RELEASE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/RELEASE.md)
- 冒烟清单：[docs/SMOKE_TEST.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/SMOKE_TEST.md)

## 许可证与第三方说明

- 项目源码许可证：[LICENSE](C:/Users/littlebai/workspace/personal/anan_subtitle/LICENSE)
- 第三方说明：[docs/THIRD_PARTY_NOTICES.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/THIRD_PARTY_NOTICES.md)
- 模型来源：[docs/MODEL_SOURCES.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/MODEL_SOURCES.md)
- PySide6 / Qt LGPL 说明：[docs/PYSIDE6_LGPL_NOTICE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/PYSIDE6_LGPL_NOTICE.md)
