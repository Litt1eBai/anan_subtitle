# MODEL SOURCES

本文档记录当前项目默认模型组合、逻辑模型标识以及模型来源说明。

## 1. 说明

当前项目通过 `FunASR AutoModel` 以逻辑模型名加载模型。  
这些逻辑名在运行时通常由 `FunASR` / `ModelScope` 生态解析并下载到本机缓存目录。

因此，本文档当前记录的是：

- 项目使用的逻辑模型标识
- 它们在项目中的用途
- 它们的来源渠道

正式对外发布前，建议再补充：

- 实际下载到的上游模型页面链接
- 该模型页面对应的许可证或使用条款
- 若同一逻辑名在上游指向发生变化时，对应的更新记录

## 2. 当前默认模型

| 逻辑模型名 | 用途 | 来源渠道 |
| --- | --- | --- |
| `paraformer-zh-streaming` | 实时识别 / 混合模式起句检测 | `FunASR AutoModel` 通过 `ModelScope` 生态解析与下载 |
| `paraformer-zh` | 非实时整句识别 | `FunASR AutoModel` 通过 `ModelScope` 生态解析与下载 |
| `fsmn-vad` | 语音活动检测（VAD） | `FunASR AutoModel` 通过 `ModelScope` 生态解析与下载 |
| `ct-punc` | 标点恢复 | `FunASR AutoModel` 通过 `ModelScope` 生态解析与下载 |

## 3. 当前模型组合

### `realtime`

- `model`: `paraformer-zh-streaming`
- `detector_model`: `paraformer-zh-streaming`
- `vad_model`: `fsmn-vad`
- `punc_model`: `ct-punc`
- 默认禁用 `vad_model`
- 默认禁用 `punc_model`

### `offline`

- `model`: `paraformer-zh`
- `detector_model`: `paraformer-zh-streaming`
- `vad_model`: `fsmn-vad`
- `punc_model`: `ct-punc`

### `hybrid`

- `detector_model`: `paraformer-zh-streaming`
- `model`: `paraformer-zh`
- `vad_model`: `fsmn-vad`
- `punc_model`: `ct-punc`

### `custom`

- 由用户手工指定：
  - `model`
  - `detector_model`
  - `vad_model`
  - `punc_model`

若启用了 `custom`，发布前应额外记录该自定义模型的真实来源与条款。

## 4. 发布时的最低要求

发布说明中至少应明确：

- 本项目使用 `FunASR` 作为 ASR 推理框架
- 默认模型通过 `FunASR` / `ModelScope` 生态获取
- 首次运行可能下载模型
- 具体使用的逻辑模型名见本文件

## 5. 后续建议补充

在第一次正式对外发布前，建议把下列内容补齐到本文件或 release note：

1. 每个默认模型对应的上游页面链接
2. 上游页面显示的许可证 / 使用条款
3. 模型缓存目录位置说明
4. 是否允许离线预置模型随包分发

## 6. 一句话结论

当前项目已经明确了默认使用的逻辑模型组合，但正式发布前仍应对这些逻辑模型在上游实际对应的模型页面和许可条款做最终核对。
