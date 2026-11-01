# 验证记录

## 0.2.3 双语教程、功能同步与原生封装

日期：2026-11-01。新增中英文完整教程、安装包内离线帮助和练习数据导出，科学模型保持原有实现。Mac 端源码回归与新增封装检查见当前机器可读摘要；四套教学文件的 CSV/XLS/XLSX、合法候选与固定回填检查通过。使用实际 BoTorch／分类模型完成四条练习的推荐、待实验排除、模拟回填和 8 条观测的留一验证；教程中的 6 张图来自这些实际输出。

[0.2.2 检查摘要](VALIDATION_V0.2.3.json)记录具体范围。Mac 安装包的冻结模型、界面、读写、导图与离线教程检查由封装脚本独立记录在 Release 的 MAC_VALIDATION-0.2.3.json 中，成功后才生成 Mac 安装包。

**Windows 按使用者要求仅进行原生构建与封装**：同步相同源码、教程和数据，检查文件与 ZIP 完整性；不启动 EXE、引擎或安装器，不做模型、GUI、安装运行验收。Windows 使用效果由用户实机验证。下文为 0.2.1 及更早的历史证据，不代表 Windows 通过了这些检查。


日期：2026-10-31。产品：NaNoBO 0.2.1。平台：Apple Silicon arm64、macOS 27.2；发布目标 macOS 14 及以上。界面库为 PySide6-Essentials / Shiboken 6.12.0。

## 0.2.1 完整模拟实验验收

本次以带噪声的合成产率、成本、选择性和分类标签完成 9 个工作流、41 轮、82 条模拟观测。每轮实际生成条件、导出、回填、保存重开并继续推荐；487 项闭环断言通过。另有 108 项经典运行时完整回归、17 项现代真实模型／冻结入口测试和 6 项模型边界检查通过。

本次修复了导入结果／撤回待实验后过期分析仍可保存、计算结束时控件启用状态，以及冻结安装包缺失 PDF 导出模块的问题。最终冻结程序额外读取真实 XLS、XLSX、CSV 并导出 15 个 PNG/PDF/SVG 文件和预测 CSV；最终结果见版本化的 release 验证报告。

- [模拟验收资料](https://github.com/wei-rui499/NaNoBO/releases/tag/v0.2.1)
- [功能覆盖矩阵（验收资料内）](https://github.com/wei-rui499/NaNoBO/releases/tag/v0.2.1)
- [模拟实验协议（验收资料内）](https://github.com/wei-rui499/NaNoBO/releases/tag/v0.2.1)
- [0.2.1 机器可读证据](VALIDATION_V0.2.1.json)

模拟实验仅验证指定功能及数学／数据流的一致性，不作为真实化学优化收益证据。下文保留先前版本的历史检查记录。

## 0.2 新增验证

- 经典运行时：`test_app / test_app_v2 / test_engine / test_space / test_io / test_analysis_view`：77 passed，18 既有科学后端集成用例默认跳过；这些引擎另做冻结实际计算。
- XLS、XLSX、工作表选择、缺失值、公式缓存、步长、线性／配比约束、候选表近重复、有限域耗尽、分类标签、同模型验证以及 PNG/PDF/SVG/CSV 导出均有覆盖。
- 源码完整 Qt→QProcess→模型→表格流程 8 项通过：三引擎基本推荐、受约束配方、Pareto、分类，以及 Pareto/分类只分析并保留原待实验。
- 现代运行时的真实 GP、qLogNEHVI、分类概率、LOOCV 和隔离 PATH 的冻结程序检查见 [当前验证摘要](VALIDATION_V0.2.1.json)。
- 最终 DMG 的签名、六项传统冻结模型和八项冻结 GUI 流程由打包脚本强制验收；实际本次结果见 DMG 内的 `MAC_VALIDATION.json`。

## 0.1 已完成的基础检查

| 检查 | 结果 | 覆盖范围 |
| --- | --- | --- |
| `CHEMBO_INTEGRATION=1 python -m pytest tests/test_engine.py tests/test_app.py -q` | 52 passed | 输入／CSV 校验、有限域耗尽、防重复、Gryffin 真训练、Chimera 多目标、Atlas GP、混合变量、原始单位约束、保存／另存为、手动回填协调，以及界面通过 QProcess 调用三引擎并把结果写回待实验表 |
| `PYTHONPATH=src python -m unittest discover -s tests -p test_modern.py -v` | 5 passed，1 项冻结入口默认跳过 | BO-MCP 原生初始设计、状态续接、已有观测的 GP、混合变量、待实验点和非法输入；冻结入口另做下述检查 |
| `scripts/smoke_frozen.py`，清洁复制的 `.app` | 六项通过 | 三个引擎各自的连续参数真训练，以及中文类别＋整数＋连续混合域的 batch=2；Gryffin 混合域同时启用 Chimera 双目标 |
| 实际原生窗口 | 通过启动和 Gryffin 按钮操作 | 可访问性树看到“模型计算中”，随后看到“已生成 2 个待实验条件”，待实验表有两行，原观测五行保留 |
| Qt 与 Torch 兼容 | 已修复并验证 | `typing_extensions` 先于 Qt 初始化；Olympus 元数据查询遵循标准 AttributeError；新版 Qt 取代旧版 native Cocoa 崩溃路径 |
| 独立现代运行时 | 已验证 | 构建完成后整体复制，保留原始 LC_RPATH；避免经典 Torch/Python 被错误链接进现代引擎 |
| 现代独立目录库依赖 | 已检查 | 252 个 Mach-O 的 `otool -L` 未发现开发环境的非系统绝对路径依赖 |
| 平台与图片插件 | 显式收集 | 保留 Cocoa、offscreen 等实际需要的插件；排除 `qpdf`，未引入 QtPdf、Charts、DataVisualization、WebEngine |

测试数据均为明确标注的合成／教学数据；通过软件测试不表示已经验证某一种化学体系的优化收益。上游数值库会产生部分弃用或数值警告，测试检查了返回条件的范围、有限值、数量和防重复行为，没有将失败训练回退为随机优化。

## 最终封装的强制检查

`scripts/package_macos.py` 在干净临时目录中复制最终应用、替换许可目录、设置版本与最低系统版本后，依次执行：

1. ad-hoc 代码签名和 `codesign --verify --deep --strict`。
2. 六项冻结模型检查，移除 Python/虚拟环境路径变量。
3. `NaNoBO --verify-ui`：真实创建 Qt 窗口，执行八个推荐／分析流程，确认三引擎及新任务结果进入表格，留一验证有真实留出行，只分析不会增加待实验。该入口只供维护者验收，不向普通用户展示配置步骤。
4. 以上全部成功后才生成 DMG，附应用源码、第三方许可和精确版本库源码。

这一步是打包脚本的实际验收逻辑，DMG 内的机器可读验证报告记录本次封装的结果。DMG 生成后还应挂载并复制到源码目录以外，确认签名与启动。

## 尚未覆盖

尚未完成 Apple Developer ID 签名和公证，本机没有可用的开发者签名身份。Windows 0.2.3 仅同步构建，实机运行待用户验证；Intel Mac 没有完整版。当前没有跨多台 Mac 的系统版本矩阵，也没有对真实化学实验做模型优劣基准。Atlas 界面限单目标；多保真、元学习和描述符输入尚未开放。联合配方约束、Pareto 和分类由 BoTorch 工作流提供。
