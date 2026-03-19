# FUNASR REFERENCE

本文档不是上游 `README_zh.md` 的完整拷贝，而是针对当前项目保留的一份精简参考。

来源：

- FunASR 上游仓库中文 README

保留目的：

- 记录当前项目真正用到的核心概念
- 保留少量初始化和调用示例
- 避免把整份上游文档继续放进本仓库

## 当前项目直接相关的点

### 1. 统一入口是 `AutoModel`

当前项目所有模型初始化都围绕：

```python
from funasr import AutoModel
```

展开。

我们的代码主要使用两类模型：

- `paraformer-zh-streaming`：实时识别
- `paraformer-zh`：非实时识别

另外常见配套模型：

- `fsmn-vad`
- `ct-punc`

### 2. 模型仓库可以显式指定

FunASR 支持通过 `hub` 控制模型来源：

- `ms`：ModelScope
- `hf`：Hugging Face

这和当前项目的模型下载修复直接相关，因为打包版现在会优先尝试 `ModelScope`，失败后再回退到 `Hugging Face`。

### 3. 非实时识别的最小调用方式

和当前项目最接近的非实时调用形态可以简化理解成：

```python
from funasr import AutoModel

model = AutoModel(
    model="paraformer-zh",
    vad_model="fsmn-vad",
    punc_model="ct-punc",
)

result = model.generate(input="demo.wav", batch_size_s=300)
```

在本项目里，这部分被封装到：

- [engine_loader.py](C:/Users/littlebai/workspace/personal/anan_subtitle/src/recognition/engine_loader.py)
- [engine_runtime.py](C:/Users/littlebai/workspace/personal/anan_subtitle/src/recognition/engine_runtime.py)
- [offline_session.py](C:/Users/littlebai/workspace/personal/anan_subtitle/src/recognition/offline_session.py)

### 4. 实时识别的关键参数

实时模型最重要的不是单纯 `generate()`，而是这组流式参数：

- `chunk_size`
- `encoder_chunk_look_back`
- `decoder_chunk_look_back`
- `cache`
- `is_final`

项目里对应收口在：

- [engine_config.py](C:/Users/littlebai/workspace/personal/anan_subtitle/src/recognition/engine_config.py)
- [realtime_session.py](C:/Users/littlebai/workspace/personal/anan_subtitle/src/recognition/realtime_session.py)

### 5. 模型目录不一定是本地路径

上游示例里 `model=` 可以是：

- 模型名
- 仓库 ID
- 本地目录

这也是当前项目要额外处理下载与缓存完整性的原因：

- 命名模型需要先下载
- 下载失败时 FunASR 本身不一定给出足够清晰的错误
- 当前项目已经在 [model_download.py](C:/Users/littlebai/workspace/personal/anan_subtitle/src/core/model_download.py) 里补了缓存校验和回退逻辑

## 当前项目需要记住的上游约束

- `AutoModel` 的下载、模型解析和配置合并并不完全透明
- `download_model_from_hub.py` 某些失败路径会吞掉底层异常
- 流式和非流式模型的调用参数结构不同
- `hub`、缓存目录和模型本地路径会直接影响初始化结果

## 建议用法

如果后续你要继续扩模型管理功能，优先参考：

1. 上游文档里的 `AutoModel` 初始化方式
2. 上游对实时模型 `chunk_size` 的说明
3. 当前项目中的：
   - [model_download.py](C:/Users/littlebai/workspace/personal/anan_subtitle/src/core/model_download.py)
   - [engine_loader.py](C:/Users/littlebai/workspace/personal/anan_subtitle/src/recognition/engine_loader.py)
   - [realtime_session.py](C:/Users/littlebai/workspace/personal/anan_subtitle/src/recognition/realtime_session.py)

## 一句话结论

这份文档只保留了 FunASR 上游 README 中和本项目直接相关的最小知识面：`AutoModel`、`hub`、实时/非实时调用差异、以及模型下载与缓存行为。
