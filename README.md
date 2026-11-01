[简体中文](README.md) | [English](README.en.md)

# NaNoBO

**把已有实验结果变成下一批值得做的实验。**

NaNoBO 是给化学研究者使用的桌面实验规划工具。你告诉它“哪些条件可以改变、哪些结果希望更好”，录入已经做过的实验，它会推荐下一批条件。做完后回填结果，再继续下一轮。

例如：温度和添加剂怎样搭配，产率可能更高？固定加液总量后，下一批该试哪些配比？产率和成本不能同时最好时，有哪些折衷方案？如果结果是“团聚／球形／棒状”，下一批怎样帮助分清形貌边界？

**安装版在本机计算，无需配置 Python、WSL、Docker 或模型 API 账户。** 当前软件界面为中文；教程和本页均可选择中文或英文。

[下载安装包](https://github.com/wei-rui499/NaNoBO/releases) · [从配套数据开始学习](docs/TUTORIAL.zh-CN.md) · [English tutorial](docs/TUTORIAL.en.md)

![NaNoBO 桌面界面：实验条件、已完成实验、下一批实验与模型分析](docs/screenshots/NaNoBO-preview.png)

## 先花十分钟跑通一轮

不必先理解算法。使用随附的**合成教学数据**，先学会这五步：

1. 在 [Releases](https://github.com/wei-rui499/NaNoBO/releases) 下载适合电脑的安装包，以及本次版本的教程数据包。0.2.3 及更新安装版的“帮助”菜单也提供教程和练习数据入口。
2. 打开练习目录 `01_quickstart/project.chembo.json`。项目已经设置好温度、循环次数和添加剂，并带有 **6 条模拟实验结果**。
3. 点击“**生成下一批实验 →**”，在“下一批 / 待实验”中查看 **2 个待做条件**。
4. 点击“导出待回填 CSV”。在 `all-simulated-results.csv` 中找到这两组完全相同的条件，将对应的模拟产率填入导出表，再从“已完成实验 → 导入 Excel / CSV”导入。
5. 保存项目，点击“**分析与交叉验证**”，查看候选预测、预测—实测图和模型误差，再规划下一轮。

[逐步操作、每步应看到什么、常见问题 →](docs/TUTORIAL.zh-CN.md#2-十分钟完成一次实验循环)

教学数值用于练习软件操作，不能作为真实化学配方或实验结论。`all-simulated-results.csv` 是练习时查数的“模拟结果库”，不要整表导入，否则相当于把全部候选都做完了。

## 下载与安装

| 电脑 | 使用方法与发布状态 |
| --- | --- |
| M 系列 Mac，macOS 14+ | 从 Releases 下载 `macOS-arm64.dmg`，打开后将 NaNoBO 拖入“应用程序”。已有经过模拟验收的安装版。 |
| Windows 10/11，x64 | 代码、教程和打包配置已与 Mac 同步；安装器以 Releases 实际提供的 `windows-x64-setup-unsigned.exe` 为准。**Windows 实机运行待验证**，见 [Windows 构建说明](docs/WINDOWS_BUILD.md)。 |
| Intel Mac / Windows ARM64 | 当前没有经过验证的对应安装版。 |

Mac 测试版尚未完成 Apple 公证；首次打开如被系统拦截，可按 [Apple 官方说明](https://support.apple.com/en-us/102445) 在“隐私与安全”中确认。Windows 未签名测试安装器也可能出现系统信誉提示；不要关闭系统安全保护。详细步骤见[完整教程](docs/TUTORIAL.zh-CN.md#1-安装与第一次打开)。

安装版已携带计算环境。下面的开发文档给维护者重建软件使用，普通使用者不用执行其中的命令。

## 我的实验能用哪些功能？

| 你想解决的问题 | 在 NaNoBO 中怎么做 | 配套练习 |
| --- | --- | --- |
| 想提高产率、选择性、信号强度，或降低粒径误差 | 设置一个数值目标，选择最大化或最小化，逐批回填实测结果 | [01：温度、添加剂与产率](examples/tutorial/01_quickstart/) |
| 移液器只能按固定档位加液，或总量必须固定 | 填写步长，设置总量、线性与配比规则，或导入允许执行的候选配方表 | [02：固定总量配方](examples/tutorial/02_recipe/) |
| 同时关心产率与成本 | 使用 Pareto 多目标，观察不同性能之间的折衷 | [03：多目标取舍](examples/tutorial/03_pareto/) |
| 结果是成功／失败、形貌类别等文字标签 | 使用分类主动学习，观察类别概率及不确定性 | [04：形貌分类](examples/tutorial/04_classification/) |
| 已有 Excel 实验表，希望少手动录入 | 导入 `.xls`、`.xlsx` 或 UTF-8 `.csv`，多工作表时选结果页 | [导入表格](docs/TUTORIAL.zh-CN.md#45-录入与导入) |
| 想知道“为什么推荐”和“模型是否可信” | 看预测均值、模型不确定性和候选排序；做同模型留一验证 | [读图与验证](docs/TUTORIAL.zh-CN.md#8-读懂模型与可视化) |
| 想保存给组会或论文作图 | 导出当前图为 PNG/PDF/SVG，导出预测和实验结果为 CSV | [导出与项目留档](docs/TUTORIAL.zh-CN.md#10-保存导出与项目记录) |

## 推荐引擎怎么选？

第一次使用，建议先沿教程使用 **BoTorch · 优化与分类**。它接入了配方限制、Pareto、分类及当前界面的模型诊断。

| 界面中的名称 | 适合的当前工作流 |
| --- | --- |
| **BoTorch · 优化与分类** | 单目标、步长／候选表／联合约束、Pareto、分类和模型分析；算法设置固定，照教程操作即可。 |
| **Gryffin · 类别与连续变量** | 使用 Gryffin 原生推荐；多个数值目标可按表中顺序设置优先级，结合 Chimera。 |
| **Atlas · 高斯过程** | 使用 Atlas 原生 GPPlanner 做单目标和批量推荐。 |

Gryffin 和 Atlas 的原生推荐不会附上另一个模型冒充的预测或交叉验证。上游软件的全部能力也不等于当前桌面界面已开放；[教程说明了各引擎的范围](docs/TUTORIAL.zh-CN.md#9-gryffinatlas-与引擎选择)。

推荐是下一步实验的建议，预测是模型的估计，只有实际测量后才成为实验结果。分类工作流优先探索不确定的类别边界，不等同于优先寻找“最容易成功”的条件。

## 教程、数据与验证

- [中文完整教程](docs/TUTORIAL.zh-CN.md) / [English tutorial](docs/TUTORIAL.en.md)：从安装、每个按钮到读图和排错。
- [配套练习文件](examples/tutorial/)：四套完整项目、空项目、回填练习及同内容的 CSV/XLS/XLSX 表格；所有数据明确标为合成。
- [功能与数据格式](docs/V0.2_FEATURES.md)：边界、字段和计算规模说明。
- [软件验证记录](docs/VALIDATION.md)：已完成的检查及其适用范围。合成实验用于验证软件流程；真实体系效果需要真实实验检验。
- [开发与重建](docs/DEVELOPMENT.md) / [Windows 构建](docs/WINDOWS_BUILD.md)：给开发者和维护者。

## 科研模型致谢、许可与引用

NaNoBO 提供桌面界面、实验记录与回填、配方空间、分析图表和安装包。**Gryffin、Phoenics、Chimera、Atlas、Olympus、BoTorch、GPyTorch、scikit-learn 及相关科研方法归各自原作者和团队所有**；保留的 BO-MCP 兼容代码也保留原有归属。NaNoBO 是独立项目。

使用本软件发表科研结果时，请同时引用 NaNoBO 和**实际使用的方法**：[公开致谢](ACKNOWLEDGMENTS.md) · [引用指南](docs/HOW_TO_CITE.md) · [14 条参考文献与软件引用](REFERENCES.bib) · [CITATION.cff](CITATION.cff)。

NaNoBO 自有代码采用 [Apache-2.0](LICENSE)；上游代码、Qt 等依赖保留各自许可证。完整声明、对应源码和修改记录见 [第三方说明](THIRD_PARTY_NOTICES.md)、[分发说明](docs/THIRD_PARTY.md)及[上游修改记录](docs/UPSTREAM_MODIFICATIONS.md)。
