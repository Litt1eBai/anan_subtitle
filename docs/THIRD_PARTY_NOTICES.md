# THIRD PARTY NOTICES

本文档用于发布包随附的第三方依赖、资源资产与分发注意事项说明。

## 1. 项目自身许可证

- 本项目自有源码采用 `MIT License`
- 许可证文件随项目与发布包一起分发：`LICENSE`

## 2. 主要第三方依赖

以下列表描述当前发布构建直接依赖的主要第三方库及其许可证信息。

| 组件 | 用途 | 许可证 / 说明 |
| --- | --- | --- |
| `PySide6` | Qt GUI 框架 | `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` |
| `sounddevice` | 麦克风音频采集 | `MIT` |
| `numpy` | 数值计算 | `BSD-3-Clause` |
| `torch` | 推理运行时 | `BSD-3-Clause` |
| `torchaudio` | 音频处理 | `BSD` / `BSD-3-Clause` 风格许可证 |
| `PyYAML` | YAML 配置读写 | `MIT` |
| `modelscope` | 模型下载与加载生态 | `Apache-2.0` |
| `funasr` | ASR 推理框架 | 当前安装包元数据与 classifier 存在不一致，发布前应继续以上游声明为准核对 |

## 3. PySide6 / Qt 分发说明

- Windows 打包产物采用 `PyInstaller` 的目录分发形式
- `PySide6` / Qt 相关运行库以动态链接方式随发布目录分发
- 发布包应随附：
  - 本文件
  - 项目 `LICENSE`
  - `PySide6` / Qt 对应的 `LGPL` 许可证文本

注意：

- 本项目源码许可证为 `MIT`，不改变第三方库各自的许可证要求
- 后续若更改 Qt 分发方式，应重新核对 `LGPL` 合规要求

## 4. 模型与运行时资源

- `FunASR` / `ModelScope` 实际使用的模型来源单独记录在 `MODEL_SOURCES.md`
- 若发布包首次运行会自动下载模型，用户应能看到模型来源说明

## 5. 第三方资源资产

### `config/base.png`

- 本项目当前默认背景图片文件：`config/base.png`
- 该图片中的人物形象及相关美术资产来源于游戏作品
- 相关角色形象、美术设计与原始版权归该游戏及其权利方所有
- 该图片资源不属于本项目 `MIT` 许可证授予范围

发布注意：

- 若对外公开分发该图片，应确认你有权以当前方式使用和分发该素材
- 如果后续需要降低版权风险，建议替换为自制素材、授权素材或明确可商用素材

## 6. 发布包应包含的合规文件

建议 Windows 发布目录至少包含：

- `LICENSE`
- `README.md`
- `THIRD_PARTY_NOTICES.md`
- `MODEL_SOURCES.md`
- `PySide6` / Qt `LGPL` 许可证文本

## 7. 一句话结论

本项目自有代码可以继续以 `MIT` 开源，但发布包仍需分别遵守 `PySide6/Qt`、模型来源以及第三方资源资产各自的许可证与使用条件。
