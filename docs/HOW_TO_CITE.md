# 如何引用 NaNoBO 和实际使用的科研方法

请同时区分 **NaNoBO 软件／界面贡献** 与 **优化、概率建模和标量化方法的原始科研贡献**。先记录项目中的实际引擎、软件版本、任务类型和运行历史，再选择对应论文；不要把本页所有论文无差别列为同一研究的方法。

## 引用 NaNoBO 软件

在 NaNoBO 的 GitHub 页面使用“Cite this repository”，或引用根目录的 [CITATION.cff](../CITATION.cff)。本版本可写为：

> NaNoBO contributors. *NaNoBO: local desktop experiment planning for chemists*, version 0.2.1 (2026). https://github.com/wei-rui499/NaNoBO

目前没有为 NaNoBO 声明论文或 DOI。`NaNoBO contributors` 是软件贡献者的团体署名，不代替各上游论文作者。若未来正式指定维护者个人署名或取得 Zenodo 等归档 DOI，应使用该版本经过确认的引用记录。

## 按实际方法选择引用

| 你的项目实际使用了什么 | 应引用的条目（对应 REFERENCES.bib） |
| --- | --- |
| Gryffin 类别／混合变量优化 | `Hase2021Gryffin` |
| Gryffin 中的连续变量方法 | 上述 Gryffin 条目，并按上游指引加 `Hase2018Phoenics` |
| Gryffin / Chimera 的优先级多目标 | 相应 Gryffin／连续方法条目，加 `Hase2018Chimera` |
| Gryffin 的已知约束接口／已测点排除 | 按上游指引加 `Hickman2022KnownConstraints`（正式发表版）；不要据此把 NaNoBO 的 BoTorch 联合配方域写成 Gryffin 功能 |
| Atlas GPPlanner | `Hickman2025Atlas`；其运行基础为 Olympus，可加 `Hase2021Olympus` 与上游请求的 `Hickman2023OlympusEnhanced`（明确为预印本） |
| 新版 BoTorch 单目标（SingleTaskGP + qLogEI） | `Balandat2020BoTorch`、`Ament2023LogEI`；GP 实现可加 `Gardner2018GPyTorch` |
| 新版 BoTorch Pareto（ModelListGP + qLogNEHVI） | `Balandat2020BoTorch`、`Daulton2021NEHVI`、`Ament2023LogEI`；GP 实现可加 `Gardner2018GPyTorch` |
| 分类主动学习（GaussianProcessClassifier + 分类熵） | `Pedregosa2011ScikitLearn`；高斯过程分类理论可引 `Rasmussen2006GPML`；NaNoBO 的候选域与回填界面另按软件引用 |
| 实际调用保留的 BO-MCP / bo-engine 兼容接口 | 另注明 `Gottstein2026BOMCP` 的软件来源与固定提交，并引用实际底层 BoTorch 方法 |

完整、可导入参考文献管理器的作者、题名、卷页及 DOI 见 [REFERENCES.bib](../REFERENCES.bib)。核对来源和差异处理见 [CITATION_VERIFICATION.json](CITATION_VERIFICATION.json)。

## 论文方法部分示例

以下句子是填写模板，必须按真实项目改写，不能用于把模拟验证写成化学实测。

**Gryffin + Chimera：**

> 实验条件通过 NaNoBO v0.2.1 桌面界面管理，并由 Gryffin 推荐。连续变量方法按 Phoenics 的原始方法引用；优先级多目标使用 Chimera 标量化。[引用 NaNoBO、Gryffin、Phoenics（如适用）、Chimera]

**BoTorch 单目标：**

> 使用 NaNoBO v0.2.1 在预定义的合法候选域中管理实验。数值响应采用 BoTorch 的 SingleTaskGP 建模，下一批候选以 qLogEI 评分，并排除已测及待实验条件。[引用 NaNoBO、BoTorch、LogEI；GPyTorch（如适用）]

**BoTorch Pareto：**

> 各数值目标由 BoTorch 的高斯过程模型拟合，候选使用 qLogNEHVI 选择；实测 Pareto 集合与超体积以报告中注明的目标方向和参考点计算。[引用 NaNoBO、BoTorch、NEHVI、LogEI]

**分类：**

> 在 NaNoBO v0.2.1 中使用 scikit-learn 的 GaussianProcessClassifier 估计已观察类别的概率，按分类熵选择需要探索的实验条件。[引用 NaNoBO、scikit-learn；GPML 理论参考]

## 不应混淆的范围

- `nanobo-botorch-v2` 是 NaNoBO 直接组合原生 BoTorch／scikit-learn 的工作流标识，不是一个声称新发明的代理模型，也不是 BO-MCP 全部服务功能。
- 选择 BoTorch／分类任务，不应将其方法统一归功于 Gryffin、Atlas 或 Alán Aspuru-Guzik 课题组。
- 本版本没有把 BayBE、BgoLearn／BgoFace 作为运行引擎。产品功能对照不等于代码使用或算法实验对比。
- Golem 等库作为依赖出现，不表示 NaNoBO 已开放其全部科学能力；只有实际采用的方法才能写入研究的方法部分。
- 留一验证使用相应工作流的实际模型；候选预测与不确定性不是已完成的化学测量。公开教学／验收数据标为 SYNTHETIC，不能写成湿实验结果。

科研引用与软件许可分别处理：引用论文不能取代完整许可证和版权声明；附带许可证也不能代替学术署名。完整声明见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) 和 [ACKNOWLEDGMENTS.md](../ACKNOWLEDGMENTS.md)。
