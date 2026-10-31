# Acknowledgments / 公开致谢

NaNoBO 是一个面向化学研究者的独立桌面实验规划界面。我们感谢下列科研软件、算法论文及其原作者和维护者；NaNoBO 的界面和安装包不改变这些成果的学术归属。

特别感谢 **Florian Häse、Loïc M. Roch、Matteo Aldeghi、Riley J. Hickman、Alán Aspuru-Guzik 及其合作者**为 Phoenics、Gryffin、Chimera、Atlas 与 Olympus 作出的贡献。感谢 **BoTorch、GPyTorch、PyTorch 与 scikit-learn** 的作者和维护者提供现代优化与概率建模基础；感谢 **Willi Gottstein / BO-MCP** 项目提供保留在本软件中的兼容后端。完整作者列表见 [REFERENCES.bib](REFERENCES.bib)。

## 实际贡献与使用范围

| 上游成果 | NaNoBO 中的实际角色 | 原始来源与论文 |
| --- | --- | --- |
| Gryffin | 经典优化引擎；连续、整数与类别变量 | [代码](https://github.com/the-matter-lab/gryffin) · [Häse et al., 2021](https://doi.org/10.1063/5.0048164) |
| Phoenics | Gryffin 连续变量方法的基础；按 Gryffin 官方引用指引致谢，并非另设一个独立桌面引擎 | [Häse et al., 2018](https://doi.org/10.1021/acscentsci.8b00307) |
| Chimera | Gryffin 工作流的优先级多目标标量化 | [代码](https://github.com/the-matter-lab/chimera) · [Häse et al., 2018](https://doi.org/10.1039/C8SC02239A) |
| Gryffin 已知约束接口 | Gryffin adapter 使用其 known_constraints 接口排除已测／待实验点；NaNoBO 新版联合配方域另由 BoTorch 路径执行 | [Hickman et al., 2022](https://doi.org/10.1039/D2DD00028H) |
| Atlas | 原生 GPPlanner 单目标／批量推荐工作流 | [代码](https://github.com/the-matter-lab/atlas) · [Hickman et al., 2025](https://doi.org/10.1039/D4DD00115J) |
| Olympus | Atlas 的参数、观测、实验规划接口及运行支持 | [代码](https://github.com/the-matter-lab/olympus) · [Häse et al., 2021](https://doi.org/10.1088/2632-2153/abedc8) · [增强版预印本](https://doi.org/10.26434/chemrxiv-2023-74w8d) |
| BoTorch | 新版数值优化、后验预测、qLogEI 和 qLogNEHVI 的实际实现 | [代码](https://github.com/pytorch/botorch) · [Balandat et al., 2020](https://papers.neurips.cc/paper_files/paper/2020/hash/f5b1b89d98b7286673128a5fb112cb9a-Abstract.html) |
| LogEI 方法 | 单目标 qLogEI 及多目标采集函数的对数稳定化 | [Ament et al., 2023](https://papers.neurips.cc/paper_files/paper/2023/hash/419f72cbd568ad62183f8132a3605a2a-Abstract-Conference.html) |
| NEHVI 方法 | 噪声多目标超体积改进，是 qLogNEHVI 的方法基础 | [Daulton et al., 2021](https://papers.neurips.cc/paper_files/paper/2021/hash/11704817e347269b7254e744b5e22dac-Abstract.html) |
| GPyTorch | Atlas／BoTorch 工作流的高斯过程基础设施 | [代码](https://github.com/cornellius-gp/gpytorch) · [Gardner et al., 2018](https://proceedings.neurips.cc/paper_files/paper/2018/file/27e8e17134dd7083b050476733207ea1-Paper.pdf) |
| scikit-learn / GPML | 分类主动学习中的 GaussianProcessClassifier 实现与高斯过程分类理论 | [Pedregosa et al., 2011](https://www.jmlr.org/papers/v12/pedregosa11a.html) · [Rasmussen & Williams, 2006](https://gaussianprocess.org/gpml/) |
| BO-MCP / bo-engine | 独立 Python 3.13 兼容后端；其固定源代码仍受 MIT 许可覆盖 | [固定源码](https://github.com/AccelerationConsortium/bo-mcp/tree/56d590b91ac120d0f22a3e41e770843d271808cd) |

新版增强工作流 `nanobo-botorch-v2` 在 NaNoBO 的 `modeling.py` 中直接组合 BoTorch／scikit-learn 的原生模型。它不等同于 BO-MCP 的完整服务产品，也不把 BoTorch、scikit-learn 或 BayBE 归为 Aspuru-Guzik 课题组原创算法。BayBE 不是本版本运行引擎。

感谢 Python、NumPy、SciPy、pandas、Matplotlib、Qt/PySide6、openpyxl、xlrd、PyInstaller、Cython、Pymoo、DEAP 以及其他依赖的开发者。Golem 作为上游依赖随包保留，但其鲁棒优化功能尚未作为 NaNoBO 的独立用户功能开放。依赖不全部是“科研模型”，其法律归属和许可仍全部保留，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [licenses/](licenses/)。

BgoFace / BgoLearn 的公开功能曾用于产品需求对照，相关过程记录在 `research/`。它们不作为 NaNoBO 的优化后端；本项目没有将其模型或界面源码并入应用，也不声称存在同条件性能优越性结论。

## NaNoBO 自身的贡献

NaNoBO 提供独立的桌面交互、严格表格输入、可执行配方域、实验回填与项目保存、引擎进程集成、实际模型诊断、结果可视化、模拟功能验收和安装包构建。科学优化方法、论文及原始软件的作者署名按各自来源保留。

NaNoBO 不是上述作者、课题组、机构或项目的官方桌面产品，以上致谢不表示他们参与、审核或背书 NaNoBO。引用论文与履行开源许可证是两件分别需要处理的事；致谢页不能替代许可证、版权声明、对应源码或修改记录。

发表使用本软件的研究时，请按[如何引用](docs/HOW_TO_CITE.md)引用实际使用的模型，不只引用 NaNoBO。
