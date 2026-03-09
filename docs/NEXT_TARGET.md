# NEXT TARGET

本文档描述下一阶段的目标，不再追踪历史迁移细节。

如果你想看目标边界，请查看 [ARCHITECTURE.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)。
如果你想看当前实现，请查看 [CURRENT_ARCHITECTURE.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/CURRENT_ARCHITECTURE.md)。

## 当前阶段目标

当前阶段不再继续大规模拆分结构，优先目标是：

1. 把项目做成可稳定分发的 Windows 版本
2. 在稳定基线上继续下一阶段功能开发

## 近期优先级

### 1. 发布准备

这是当前最高优先级。

需要补齐：

- Windows `exe` 打包链路
- 人工冒烟清单
- 至少一条端到端发布验证路径
- 依赖版本收敛
- 分发合规材料

### 2. 保持结构稳定

当前不建议继续机械拆分：

- `recognition/engine.py`
- `presentation/qt/overlay_window.py`
- `presentation/qt/settings_window.py`

后续只在真实功能开发中遇到痛点时，再局部调整。

### 3. 进入下一轮功能开发

在发布准备完成后，再继续推进：

- 更多字幕样式预设
- 用户体验打磨
- 模型管理体验
- Windows 发布体验

## 发布准备任务

### Windows 打包

- 增加 `PyInstaller` 方案
- 增加打包脚本
- 明确输出目录
- 明确资源拷贝规则

### 运行态配置策略

- 明确 `app.yaml` 的用户目录落点
- 首次启动时从 `default.yaml` 生成运行态配置
- 避免把运行态配置作为发布基线的一部分

### 依赖收敛

- 固定核心依赖版本
- 明确 Python 版本
- 保证构建结果可重复

### 合规材料

- `PySide6` 动态链接分发
- `LGPL` 声明随包
- 第三方许可证说明
- 模型来源说明

### 发布验证

- 启动
- 首次模型选择
- 模型下载
- 麦克风输入
- 实时/非实时识别
- 托盘交互
- 保存配置
- 退出重启

## 不在当前阶段处理的事

以下内容暂时不作为当前阶段主目标：

- 新一轮大规模架构拆分
- 跨平台实现
- 高自由度样式编辑器
- 高复杂度插件系统

## 一句话结论

当前阶段的下个目标不是继续重构，而是完成发布准备，并把当前代码库推进到可稳定分发的 Windows 版本。
