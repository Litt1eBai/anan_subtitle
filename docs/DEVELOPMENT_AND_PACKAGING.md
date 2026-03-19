# DEVELOPMENT AND PACKAGING

本文档只描述开发与打包流程。

如果你想看：

- 文档总入口： [INDEX.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/INDEX.md)
- 架构与现状： [ARCHITECTURE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)、[CURRENT_ARCHITECTURE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/CURRENT_ARCHITECTURE.md)
- 发布流程： [RELEASE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/RELEASE.md)
- 冒烟清单： [SMOKE_TEST.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/SMOKE_TEST.md)

## 1. 开发流程

### 环境准备

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-lock.txt
```

如果需要构建发布包：

```powershell
pip install -r requirements-build-lock.txt
```

### 依赖文件说明

- `requirements.txt`：运行依赖的范围声明
- `requirements-build.txt`：构建依赖的范围声明
- `requirements-lock.txt`：当前已验证的运行依赖锁定版本
- `requirements-build-lock.txt`：当前已验证的构建依赖锁定版本

当前锁定环境基于 `Python 3.14.2` 验证。

### 开发运行

推荐直接运行源码入口：

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe src\main.py --config config\app.yaml
```

或继续使用：

```powershell
start.bat
```

### 开发验证

提交前至少执行：

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall src
```

### 开发迭代建议

建议按这个顺序迭代：

1. 改代码
2. 跑测试
3. 如改动影响发布链，额外跑一次打包
4. 更新 README / docs
5. 再提交

## 2. 打包流程

### 构建命令

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build-lock.txt
.\scripts\build_windows.ps1
```

### 打包原理

当前项目使用 `PyInstaller` 进行 Windows 打包。

- 入口脚本：`src/main.py`
- 构建描述文件：`pyinstaller.spec`
- 构建脚本：`scripts/build_windows.ps1`

`PyInstaller` 会：

1. 分析 `main.py` 的导入链
2. 收集 Python 运行时、依赖库、动态库
3. 按 `pyinstaller.spec` 额外加入资源文件
4. 生成 `dist/anan_subtitle/` 目录

### 打包后目录

发布目录位于：

```text
dist/anan_subtitle/
```

主要内容包括：

- `anan_subtitle.exe`
- `_internal/`
- `LICENSE`
- `README.md`
- `SMOKE_TEST.md`
- `THIRD_PARTY_NOTICES.md`
- `MODEL_SOURCES.md`
- `PYSIDE6_LGPL_NOTICE.md`

注意：

- 用户运行时需要整个目录，不是单独一个 `exe`
- `_internal/` 不可删除

### 快速清理

默认清理以下内容：

- `build/`
- `dist/`
- `tests/.tmp`
- `tests/tmp_*`
- 项目内 `__pycache__`
- 项目内 `*.pyc`

命令：

```powershell
.\scripts\clean.ps1
```

如果要同时清掉打包版用户目录数据，并重新触发首次启动流程：

```powershell
.\scripts\clean.ps1 -IncludeUserData
```

`-IncludeUserData` 会删除 `%LOCALAPPDATA%\anan_subtitle\` 下的运行态配置、日志和模型缓存。

### 打包资源

当前随包带上的项目资源包括：

- `config/default.yaml`
- `config/base.png`

运行时行为：

- 打包版默认在 `%LOCALAPPDATA%\anan_subtitle\config\app.yaml` 生成用户配置
- 首次运行若没有配置，会从包内模板生成
- 打包版默认数据目录：`%LOCALAPPDATA%\anan_subtitle\data`
- 打包版默认日志目录：`%LOCALAPPDATA%\anan_subtitle\logs`
- 首次启动和设置面板都支持把数据目录、日志目录改为软件目录 / 用户目录 / 自定义目录
- 默认日志文件：`desktop_subtitle.log`

## 3. 合规文件

当前发布目录应包含：

- `LICENSE`
- `THIRD_PARTY_NOTICES.md`
- `MODEL_SOURCES.md`
- `PYSIDE6_LGPL_NOTICE.md`

其中：

- `THIRD_PARTY_NOTICES.md`：第三方依赖与资源资产说明
- `MODEL_SOURCES.md`：默认模型组合与来源说明
- `PYSIDE6_LGPL_NOTICE.md`：PySide6 / Qt LGPL 分发提示

## 4. 一句话结论

开发时跑源码入口，发布时跑 `build_windows.ps1`，最终对外分发的是整个 `dist/anan_subtitle/` 目录。
