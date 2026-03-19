# NEXT TARGET

本文档只描述当前阶段目标和下一阶段工作面，不再重复开发、打包和发布细节。

如果你想看目标边界，请查看 [ARCHITECTURE.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)。
如果你想看当前实现，请查看 [CURRENT_ARCHITECTURE.md](/C:/Users/littlebai/workspace/personal/anan_subtitle/docs/CURRENT_ARCHITECTURE.md)。
如果你想看开发和发布流程，请查看 [DEVELOPMENT_AND_PACKAGING.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/DEVELOPMENT_AND_PACKAGING.md) 和 [RELEASE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/RELEASE.md)。

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

当前已建立首版 `PyInstaller` 构建链路，接下来优先验证打包产物、补齐冒烟记录和收敛发布依赖。

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

## 当前聚焦

下一阶段只聚焦两件事：

1. 完成可稳定分发的 Windows 版本
2. 在稳定基线上继续推进产品功能

具体执行流程和检查项不再放在这里，统一查看：

- [DEVELOPMENT_AND_PACKAGING.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/DEVELOPMENT_AND_PACKAGING.md)
- [RELEASE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/RELEASE.md)
- [SMOKE_TEST.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/SMOKE_TEST.md)

## 不在当前阶段处理的事

以下内容暂时不作为当前阶段主目标：

- 新一轮大规模架构拆分
- 跨平台实现
- 高自由度样式编辑器
- 高复杂度插件系统

## 一句话结论

当前阶段的下个目标不是继续重构，而是完成发布准备，并把当前代码库推进到可稳定分发的 Windows 版本。
