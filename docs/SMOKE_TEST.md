# SMOKE TEST

发布前至少执行一轮人工冒烟，确认 Windows 打包产物可正常运行。

## 构建前

- 工作区干净
- `python -m unittest discover -s tests -v` 通过
- `python -m compileall src` 通过

## 打包验证

1. 执行 `scripts\build_windows.ps1`
2. 确认生成 `dist\anan_subtitle\anan_subtitle.exe`
3. 确认发布目录内包含：
   - `LICENSE`
   - `README.md`
   - `config` 资源已被打进程序

## 运行验证

1. 双击启动 `anan_subtitle.exe`
2. 首次运行确认会在用户目录生成 `app.yaml`
3. 选择模型组合
4. 若启用下载，确认模型下载流程正常
5. 说话后确认字幕正常出现
6. 切换实时/非实时配置并保存
7. 关闭并重新启动，确认配置能恢复
8. 托盘显示/隐藏正常
9. 退出后进程正常结束

## 记录建议

每次发布前记录：

- 构建提交号
- Python 版本
- Windows 版本
- 是否首次下载模型
- 冒烟结果
- 遗留问题
