# NaNoBO

**面向化学研究者的本地桌面贝叶斯优化工具。** 定义实验变量，导入测量结果，推荐下一批条件，做完实验后回填；最终用户无需安装 Python、WSL、Docker，也无需模型 API 账户。

NaNoBO 是独立开发的桌面界面。Gryffin、Atlas、BoTorch 等科研模型和数值方法归原作者所有；NaNoBO 的贡献是界面、实验数据管理、可执行配方空间、分析可视化和桌面分发集成。请阅读 [公开致谢](ACKNOWLEDGMENTS.md)、[如何引用](docs/HOW_TO_CITE.md)、[第三方声明](THIRD_PARTY_NOTICES.md) 和 [完整参考文献](REFERENCES.bib)。

## 下载与使用

- [安装包和验证资料](https://github.com/wei-rui499/NaNoBO/releases)：当前提供 Apple Silicon（M 系列）Mac 测试版，目标系统 macOS 14+。
- [操作说明](docs/使用说明.md)：从建项目到回填下一轮实验。
- [功能说明](docs/V0.2_FEATURES.md) · [模拟验收](docs/VALIDATION.md)。

打开 DMG，将 NaNoBO.app 拖入 Applications。当前版本采用本地 ad-hoc 签名，尚未完成 Apple Developer ID 签名／公证；不需要上架 App Store。网上下载后 macOS 可能要求用户在“隐私与安全”中确认首次打开，见 [Apple 官方操作说明](https://support.apple.com/en-us/102445)。

Windows 和 Intel Mac 尚无已验证安装包；Windows 按当前开发安排暂缓。本仓库没有默认启动 Windows 构建的 CI。

## 可以做什么

| 工作流 | 当前支持 |
| --- | --- |
| 变量与实验记录 | 连续、整数、类别变量；XLS/XLSX/CSV 导入；选择 Excel 工作表；保存／重开项目；待实验回填与防重复 |
| 可执行配方 | 原单位步长、合法候选表、总量／线性规则和配比限制；增强工作流使用 BoTorch |
| 数值优化 | 单目标最大化／最小化；批量推荐；预测均值、模型标准差、候选采集分值与排序 |
| 多目标 | Gryffin/Chimera 优先级目标；BoTorch Pareto，支持二维／三维图及固定参考点的超体积历史 |
| 分类主动学习 | 成功／失败、多类别标签；类别概率、分类熵、类别计数和混淆矩阵 |
| 分析与导图 | 同模型留一验证、RMSE/MAE/R²、预测—实测与误差图、分布和历史；PNG/PDF/SVG/CSV 导出 |

没有新增模型或采集函数的选择菜单。分类熵用于探索类别边界，不等同于优先推荐“最容易成功”的配方。推荐值不是测量结果，也不保证全局最优。

## 实际调用的科研方法

| 引擎／组件 | NaNoBO 的使用范围 | 原始来源 |
| --- | --- | --- |
| Gryffin | 原生连续／整数／类别推荐；多目标结合 Chimera | [the-matter-lab/gryffin](https://github.com/the-matter-lab/gryffin) |
| Atlas | 原生 GPPlanner，单目标及混合变量／批量 | [the-matter-lab/atlas](https://github.com/the-matter-lab/atlas) |
| BoTorch / GPyTorch | SingleTaskGP + qLogEI；ModelListGP + qLogNEHVI | [BoTorch](https://github.com/pytorch/botorch) · [GPyTorch](https://github.com/cornellius-gp/gpytorch) |
| scikit-learn | GaussianProcessClassifier 分类主动学习 | [scikit-learn](https://scikit-learn.org/) |
| Olympus、Chimera | 实验空间／运行接口和优先级多目标组件 | [Olympus](https://github.com/the-matter-lab/olympus) · [Chimera](https://github.com/the-matter-lab/chimera) |
| BO-MCP / bo-engine | 保留原生兼容接口；新增桌面增强工作流直接调用 BoTorch/scikit-learn | [AccelerationConsortium/bo-mcp](https://github.com/AccelerationConsortium/bo-mcp) |

这些是不同团队的成果，不能全部归为同一课题组原创。BayBE、RDKit 和 MCP 服务没有作为本桌面版本运行后端一起集成；上游框架的完整功能不等于当前界面已开放。

## 验证与范围

本机 macOS arm64 验收：**9 个模拟工作流、41 轮、82 条合成观测、487 项闭环断言**；另有 **108 项经典运行时回归、17 项现代模型测试、6 项边界检查**通过。最终安装副本通过 12 项推荐／分析／表格读取／导出检查。

所有模拟数据明确标注为合成；它们验证软件功能、数据流与数学一致性，不证明真实化学性能，也没有证明优于其他优化器。精确证据见 [验证记录](docs/VALIDATION.md)；完整结果、可重开项目和 45 张图的三格式导出在 Releases 的模拟验收资料 ZIP 中。

有限候选源组合最多 200,000 个，一次评分最多 4,096 个合法未测候选；连续空间使用固定种子的有界采样。留一验证最多选择 30 个留出点。更详细的限制见 [功能说明](docs/V0.2_FEATURES.md)。

## 源码结构

```text
src/chembo/       桌面程序、输入校验、优化接口与图表
scripts/         获取固定上游、环境构建、打包和模拟验收
tests/          数据、模型、界面和恢复流程测试
upstream/        精简且固定提交的上游源码，保留原许可与修改标记
licenses/        上游及第三方许可证、版权和版本清单
docs/            使用、构建、学术引用与验证说明
examples/        明确标注的合成教学项目
```

本仓库不提交虚拟环境、构建缓存、用户实验数据和大型安装包。科学模型的固定 SHA 与本地兼容调整见 [上游修改记录](docs/UPSTREAM_MODIFICATIONS.md)。旧的实验性构建流程仅作为文档保留在 `docs/ci-examples/`。

## 开发与重建

请按 [开发与重建](docs/DEVELOPMENT.md) 创建相互隔离的 Python 3.10／3.13 环境。构建原生应用使用 `scripts/build.py --bundle-only`；DMG 封装还需要当前验证资料及对应库源码，不能把本地发布者的历史验证报告当作新机器已经通过的结果。

## 许可与引用

NaNoBO 自有代码为 **Apache-2.0**；第三方和上游组件保留各自许可证，不被根目录许可覆盖。论文引用与许可证义务分别履行：保留版权、许可、适用 NOTICE 和源码提供义务，同时按实际使用的模型引用原始论文。

- [致谢与贡献归属](ACKNOWLEDGMENTS.md)
- [如何引用 NaNoBO 和各模型](docs/HOW_TO_CITE.md)
- [BibTeX 文献库](REFERENCES.bib) · [GitHub 引用元数据](CITATION.cff)
- [第三方许可声明](THIRD_PARTY_NOTICES.md) · [详细分发说明](docs/THIRD_PARTY.md)

NaNoBO 不代表上游团队官方产品，也不暗示原作者背书。
