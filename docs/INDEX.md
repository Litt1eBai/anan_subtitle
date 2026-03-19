# DOCUMENT INDEX

本文档是项目文档入口，用于说明文档分层和阅读顺序。

## 分层

### 第 1 层：总入口

- [README.md](C:/Users/littlebai/workspace/personal/anan_subtitle/README.md)
  - 项目简介
  - 快速开始
  - 常用文档入口

### 第 2 层：架构与现状

- [ARCHITECTURE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)
  - 目标架构
  - 长期边界
- [CURRENT_ARCHITECTURE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/CURRENT_ARCHITECTURE.md)
  - 当前真实实现
  - 当前偏重模块和约束
- [NEXT_TARGET.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/NEXT_TARGET.md)
  - 当前阶段目标
  - 下一阶段工作面

### 第 3 层：开发与交付

- [DEVELOPMENT_AND_PACKAGING.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/DEVELOPMENT_AND_PACKAGING.md)
  - 开发环境
  - 开发验证
  - Windows 打包
  - 清理与重置
- [RELEASE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/RELEASE.md)
  - 版本发布流程
  - 版本策略
  - 发布前要求
- [SMOKE_TEST.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/SMOKE_TEST.md)
  - 发布前人工冒烟清单

### 第 4 层：合规材料

- [THIRD_PARTY_NOTICES.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/THIRD_PARTY_NOTICES.md)
  - 第三方依赖和资源说明
- [MODEL_SOURCES.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/MODEL_SOURCES.md)
  - 模型来源与说明
- [PYSIDE6_LGPL_NOTICE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/PYSIDE6_LGPL_NOTICE.md)
  - PySide6 / Qt LGPL 分发提示

### 第 5 层：外部参考摘录

- [FunASR_README_zh.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/FunASR_README_zh.md)
  - 从 FunASR 上游 README 提取的项目相关参考
  - 只保留当前代码用得到的初始化和下载要点

## 推荐阅读顺序

### 新加入项目时

1. [README.md](C:/Users/littlebai/workspace/personal/anan_subtitle/README.md)
2. [CURRENT_ARCHITECTURE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/CURRENT_ARCHITECTURE.md)
3. [ARCHITECTURE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/ARCHITECTURE.md)
4. [NEXT_TARGET.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/NEXT_TARGET.md)

### 日常开发时

1. [CURRENT_ARCHITECTURE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/CURRENT_ARCHITECTURE.md)
2. [DEVELOPMENT_AND_PACKAGING.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/DEVELOPMENT_AND_PACKAGING.md)
3. 需要发布时再看 [RELEASE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/RELEASE.md)

### 发布前

1. [RELEASE.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/RELEASE.md)
2. [SMOKE_TEST.md](C:/Users/littlebai/workspace/personal/anan_subtitle/docs/SMOKE_TEST.md)
3. 合规文档 3 份

## 一句话原则

- `README` 只保留入口和快速开始
- 架构文档只讲结构
- 流程文档只讲怎么做
- 合规文档只讲分发材料
