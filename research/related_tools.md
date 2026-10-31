# Alán Aspuru-Guzik 相关实验优化工具核查

核查日期：2026-10-31。这里把“Alan 课题组”理解为 Alán Aspuru-Guzik / Matter Lab。下列结论区分官方文档声明与本机实际验证；是否已在应用中可用，应以应用测试记录为准。

## 建议整合次序

1. **Gryffin + Atlas 作为两个实验建议引擎**，共用参数、实验记录、CSV 和项目保存界面。Gryffin 的类别描述符建模与 Atlas 的高斯过程是不同路线；不能凭发表年代断言哪个对特定实验更好。
2. **Chimera 做多目标偏好设置**，不是独立 BO 引擎。应让用户声明目标优先级、方向及容忍阈值，并显示该选择改变了优化问题。
3. **BO-MCP 作为 2026 年的新一代候选重点保留**。优先研究其 `bo-engine` 独立库，避免为了本地实验建议引入整套数据库、Docker、MCP 服务和大模型。其 Python ≥3.13 与 Atlas 官方推荐的 Python 3.9/3.10 不兼容，因此宜放到独立进程及独立运行时。
4. Olympus 可用于内部基准与 Atlas 的参数/观测数据结构；Golem 可后续做参数误差下的稳健性评估；Gemini 仅在有高/低保真两套数据时有价值。无需将这些辅助工具伪装成多个同级“优化模型”。

## 官方项目与角色

| 工具 | 角色与证据 | 许可 | 安装与封装判断 |
|---|---|---|---|
| [Gryffin](https://github.com/the-matter-lab/gryffin) | 连续、离散、类别及混合空间的实验建议算法 | Apache-2.0 | 作为用户指定的核心；实际依赖、编译与平台测试见本项目构建记录 |
| [Atlas](https://github.com/the-matter-lab/atlas) | 基于 GP/BoTorch/GPyTorch 的实验 BO；官方列出混合参数、多目标、约束、多保真和元学习功能 | MIT | README 明确推荐 Python 3.9/3.10，当前不支持 ≥3.11；不能直接与最新 Python 合并 |
| [Chimera](https://github.com/the-matter-lab/chimera) | 按优先级和阈值把多个目标转换为标量效用 | MIT | `matter-chimera`；依赖 Python≥3、NumPy；适合界面内的多目标模块 |
| [Olympus](https://github.com/the-matter-lab/olympus) | 优化器基准框架、实验数据集、参数与 campaign 数据结构 | MIT | PyPI 包名 `olymp`；官方 Atlas 示例使用 Olympus；Atlas README 推荐 `olympus-atlas` 分支，不能用旧 PyPI 包替代后就假设 API 一致 |
| [Golem](https://github.com/the-matter-lab/golem) | 面向输入参数不确定性的稳健优化/历史数据稳健性分析，可配合不同优化器 | MIT | `matter-golem`；NumPy/SciPy/Pandas/scikit-learn；旧 PyPI 二进制仅列 CPython 3.7/mac x86_64，需要目标平台源码编译或核实新源码 |
| [Gemini](https://github.com/the-matter-lab/gemini) | 高/低保真数据的动态偏差校正预测；可向 Gryffin 提供代理预测模型 | MIT | README 展示 TensorFlow 2.4.1 GPU 时代环境；需双保真数据和单独兼容性测试，不能当普通单保真 BO 按钮 |
| [Phoenics](https://github.com/the-matter-lab/phoenics) | 较早的 Bayesian kernel density 实验优化器，支持批次和 Chimera | Apache-2.0 | 官方仓库 README 的环境是 Python3.6/PyMC3 3.2/Theano1.0.1 或 Edward1.3.5/TF1.4.1；现代 Apple Silicon/Windows 首发移植成本高，功能与 Gryffin 部分重叠 |
| [BO-MCP](https://github.com/AccelerationConsortium/bo-mcp) | BO 服务及可独立使用的 BO 引擎；BoTorch/BayBE 后端 | MIT | Python≥3.13；pre-1.0 明确无 API 向后兼容承诺；宜固定 commit 与运行时，具体接口见 `bo_mcp_api.md` |

旧 `https://github.com/aspuru-guzik-group/{gryffin,atlas,chimera,olympus,golem,gemini,phoenics}` 在核查时重定向至 `the-matter-lab`，应在溯源中保存重定向后的地址。

## Atlas 的具体适配点

[官方安装与示例](https://github.com/the-matter-lab/atlas/blob/main/README.md)及[安装元数据](https://github.com/the-matter-lab/atlas/blob/main/setup.py)显示：包名 `matter-atlas`，核心 `GPPlanner(goal='minimize', num_init_design=5)`，调用 `set_param_space(...)` 与 `recommend(campaign.observations)`，实测结果写入 `Campaign.add_observation(...)`。最低声明 Python≥3.9；依赖含 `botorch>=0.8.5`、`pandas<=2.0.3`、`matplotlib<=3.7.3`、`matter-chimera` 和 `matter-golem`。

[requirements.txt](https://github.com/the-matter-lab/atlas/blob/main/requirements.txt)还包含 TF2.15、TFP0.23、protobuf3.20 等较重资源。应按照应用实际使用路径确认依赖，不能把完整研究开发环境不加区分地塞入安装包。README 宣称的高级能力也不等于桌面界面全部已实现。

## 2026 年更新线索

Matter Lab 组织页近期出现 [La Agente Óptima artifacts](https://github.com/the-matter-lab/La-Agente-Optima-artifacts)，其中将 Óptima 描述为带 BO 专家子代理的自驱实验协调框架，并明确链接 [AccelerationConsortium/bo-mcp](https://github.com/AccelerationConsortium/bo-mcp) 作为 BO 后端。因此 BO-MCP 是有明确来源关系的较新候选，而不是凭项目同名猜测。

Óptima 的 artifacts 仓库主要是原始结果、审计元数据和绘图材料；主页未显示软件 LICENSE，不能据此认定整套 Óptima 程序可直接再发布。BO-MCP 自身有独立 MIT 许可证。BayBE 是其集成后端，不应归称为 Alan 课题组原创算法。

[CDMX BayesOpt](https://github.com/the-matter-lab/cdmx-bayesopt) 是 2026 年的 MIT 教学项目，固定为 Radxa ZERO 3W 上 RGB 三变量、NeoPixel/TCS34725 硬件实验；它提供教学界面参考，但不能当通用化学优化库直接加入。

## 版本与验证边界

PyPI 可核实 `matter-chimera 1.0`（2021-01-19）、`matter-golem 1.0`（2021-03-08）和 `olymp 0.0.1b0`（2020-10-14）。这些是发行记录，不是当前 GitHub 最后维护日期。Phoenics 的 PyPI 描述指向 `chemos-inc`，与 Matter Lab 老仓库存在来源差异，封装时必须明确选择哪一个实现。

官方 GitHub HTML 的“Latest commit”字段在检索返回中为空；不能从网页抓取日期推断源码日期。已下载源码固定记录：Atlas `ebb1f4f728107f759c48289c2faecfa3af19254f`（2025-05-21）；Gryffin `fb149d18f9c81b96179cc682c46e05db60bc7229`；BO-MCP `56d590b91ac120d0f22a3e41e770843d271808cd`（2026-09-18）。此报告完成角色、许可和文档/API 核查，不声称所有辅助包已在 Mac/Windows 实测。

## 主要原始来源

- [Atlas 官方文档](https://matter-atlas.readthedocs.io/en/latest/)
- [Atlas 原始 LICENSE](https://github.com/the-matter-lab/atlas/blob/main/LICENSE)
- [Chimera 官方 PyPI](https://pypi.org/project/matter-chimera/)
- [Golem 官方 PyPI](https://pypi.org/project/matter-golem/)
- [Olympus 官方 PyPI](https://pypi.org/project/olymp/)
- [BO-MCP 原始 LICENSE](https://github.com/AccelerationConsortium/bo-mcp/blob/main/LICENSE)

## 本项目实现状态补记

BO-MCP 的独立 Python3.13 worker 已实现，未改上游算法；Mac arm64 的真实源码测试及最终 onedir 冻结三轮（初始设计→pending续接→已观测GP）已通过。界面当前仅开放单目标，相关源码、状态协议、精确依赖与性能记录见 `bo_mcp_api.md`。这项验证不能代替 Windows 原生验收，也不表示本表所有辅助项目都已集成为功能。
