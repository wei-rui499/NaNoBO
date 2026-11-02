# 固定来源及修改记录

核对日期：2026-11-02。

| 来源 | 固定提交 | 本地处理 |
|---|---|---|
| the-matter-lab/gryffin | fb149d18f9c81b96179cc682c46e05db60bc7229 | 用 Cython 3.3.0 从未修改的两个 `.pyx` 重生成 `.c`，解决旧生成代码与 Python 3.10 的兼容问题；重生成文件有显著修改标记；内存统计工具兼容 Windows 缺少 Unix resource 模块的情况，无法统计时明确显示 unavailable，不影响优化计算 |
| the-matter-lab/atlas | ebb1f4f728107f759c48289c2faecfa3af19254f | 使用原生 GPPlanner；适配层显式选择 Pymoo 采集优化器处理非连续变量或批量。Pymoo known_constraints 包装器修复为先将内部索引/类别编码还原到实际变量，再评估约束，防止排除错条件；修改行有显著标记。未改变 GP 或采集函数公式 |
| the-matter-lab/olympus，olympus-atlas 分支 | def3dda70c981c667aed40a3e8a7d8143b284887 | 只下载运行源码/元数据，不下载超过 1GB 的研究数据集和训练模型；setup.py 固定源码快照版本；插件加载器对不存在的 Python `__dunder__` 元数据抛出标准 AttributeError，避免 Qt 的源代码检查把它误认成插件名 |
| AccelerationConsortium/bo-mcp | 56d590b91ac120d0f22a3e41e770843d271808cd | 兼容路径保留 bo-engine 的原生 BoTorchBackend；独立 Python 3.13 进程。v0.2 增强工作流在 NaNoBO modeling.py 中直接使用 BoTorch / scikit-learn；未把可选 BayBE/RDKit/MCP 服务一起装入 |

没有改写模型公式，没有拿随机搜索代替训练失败。类别描述符等未接入能力见 README。

Windows Hotfix1 补齐 Gryffin 两个计算路径中的内存统计日志：系统不能提供统计时输出 unavailable，避免计算完成后对 None 做数值格式化而丢失整批建议。Olympus 的 campaigns 包延迟导出 Campaign，允许 Dataset 先加载 ParameterSpace，切断包括 data_transformer 在内的循环依赖；未使用的 Olympus 基准运行器和 Plotter 同样延迟加载，日常模型推荐不要求安装 seaborn。公开类名及显式导入接口保留。

Gryffin 整数变量的扰动按内部零起始编号范围裁剪，修复原实现误用用户上下限导致的越界及遗漏选项；连续变量的边界处理保持一致。新增正、负和零起始整数边界回归，并用实际冻结模型验证有限域和最大批量。

Atlas 单条连续推荐同样固定使用其原生 Pymoo 采集优化器，避免上游梯度路径未识别 KnownConstraints 容器而返回已测边界点；GP 与采集函数不变，不切换引擎或采用随机补救。

NaNoBO 的经典工作进程在启动时把现有 stdout/stderr 管道配置为 UTF-8，并处理无控制台的情况，避免 Atlas 的 Unicode 日志在中文 Windows 的 GBK 默认编码下中断计算。修复随 bootstrap 重建流程和冻结模型验收一起保留。

公开源码省略 Gryffin 上游遗留的两个 `.pyxbldc` 文件。它们是 Python 2.7 生成的构建配置字节码缓存，包含上游开发机器路径；当前构建使用保留的 `.pyx`、`.pyxbld` 和 `.c` 源文件，不依赖这些缓存。原始缓存仅保存在本地历史档案，不随公开源码分发。

冻结应用通过自定义启动 hook 在 Qt 初始化前导入 `typing_extensions`，处理 Qt 类型注解与 Python 3.10／PyTorch 的兼容问题。当前分发的 PySide6 版本为 6.12.0；该兼容处理不改变科学计算。

新增的输入校验、CSV、项目保存、GUI、子进程适配、排除已测/待实验条件和打包脚本属于 NaNoBO。上游项目保存各自的 LICENSE。现代引擎依赖清单与经典引擎分开收集，避免把同名不同版本依赖误当成同一个。

## v0.2 增强工作流的科学归属

`src/chembo/modeling.py` 直接调用 BoTorch 的 SingleTaskGP、ModelListGP、qLogExpectedImprovement 和 qLogNoisyExpectedHypervolumeImprovement，以及 scikit-learn 的 GaussianProcessClassifier。NaNoBO 实现候选域筛选、任务编排和同模型留一重拟合，不把这些已有模型／采集函数宣称为自研新算法。BO-MCP 兼容实现与新版增强路径分开记录，不能将二者的原始作者归属混同。

原作者公开致谢见 [ACKNOWLEDGMENTS.md](../ACKNOWLEDGMENTS.md)，实际方法的引用选择见 [HOW_TO_CITE.md](HOW_TO_CITE.md)，完整条目见 [REFERENCES.bib](../REFERENCES.bib)。已有的版权、许可证、修改行标记及固定来源记录继续保留。
