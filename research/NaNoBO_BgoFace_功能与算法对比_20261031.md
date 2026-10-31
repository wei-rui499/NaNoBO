# NaNoBO 与 BgoFace：功能、算法与改进优先级

核查日期：2026-10-31。范围：当前 NaNoBO 0.1.0 的实际界面与源码、BgoFace 官方源码和手册、MultiBgolearn 固定源码，以及作者论文。没有运行 BgoFace Windows 二进制，也没有完成双方同条件优化基准。本轮只调研，不修改 NaNoBO 应用或安装包。

## 结论

BgoFace 与 NaNoBO 的目标接近，都是降低实验研究者使用贝叶斯优化的门槛。BgoFace 已有若干 NaNoBO 尚未开放的界面能力，尤其是候选表导入、原单位步长、模型/采集函数选择、数据分布图与留一验证、分类主动学习，以及 EHVI 多目标接口。

NaNoBO 已有 Mac 原生安装包、三个真实优化引擎、明确的连续/整数/类别参数、实验项目保存和 pending 回填管理。这些构成自己的产品基础，不能等价为优化性能已经优于 BgoFace。

“我们的算法应该更好”目前是待验证判断。Atlas/BoTorch 的实现与扩展能力适合作为主力基础，但优化效果依赖任务、编码、噪声、初始点、采集函数与实验预算。引擎数量、团队知名度和发表年份都不能替代同条件比较。

## 固定版本

- BgoFace：`133b540f5f73c247f04cba6bb3d1f954aedfc537`，2026-07-09；最新正式发行 5.0.0 发布于 2025-04-01。核对后，5.0.0 根目录 `main.py` 与上述提交的 `src/main.py` 内容相同，文件只是移动过位置。
- MultiBgolearn：`c960d2623ce10fbedbbfcb677b45f810f41d8e21`，2026-07-10。
- Bgolearn：官方固定提交 `9006fdf1bb9a8c2238b02566834acd49e0206acb`，2026-08-30；本轮核心算法细读集中在 MultiBgolearn，不能声称完成 Bgolearn 全仓库算法审计。
- 作者论文：[arXiv v2，2026-07-09](https://arxiv.org/html/2601.06820v2)，页面注明发表于 npj Computational Materials，DOI 10.1038/s41524-026-02226-3。

## 对方已经接入 GUI、我们尚没有的功能

| 功能 | BgoFace 已核对实现 | NaNoBO 0.1.0 | 直接用途 |
| --- | --- | --- | --- |
| Excel 输入与候选表导入 | 观测和未测候选空间可分别读 XLS/XLSX/CSV | 当前只导入包含完整测量目标的 CSV，不能把无结果候选表当搜索空间 | 先列出允许执行的配方，再只从表中选择 |
| 原单位数值步长 | 每个轴设置 min/max/step，再生成笛卡尔积 | 连续无指定步长；整数仅上下限内全部整数，需要自己换算档位 | 直接表达每次加液 5 μL、温度每档 2 °C |
| 模型与采集函数选择 | 单目标 GUI 有 GPR/SVM/RF/AdaB/MLP，及 EI、EI_plugin、Augmented_EI、EQI、Reinterpolation_EI、UCB、PoI、PES、Knowledge_G 等入口 | 当前选择的是三个预配置引擎，没有相同级别的可视化细项选择 | 调整探索/利用并比较不同响应模型 |
| 数据诊断及导图 | 直方图、类别频数、箱线图、LOOCV 预测-实测散点，相关系数、RMSE，PNG 输出 | 当前仅首个目标历史最佳值曲线 | 查看样本覆盖和预测误差 |
| 分类主动学习 | GaussianProcess/LogisticRegression/NaiveBayes/SVM/RandomForest 分类器；Least Confidence、Margin、Entropy 采样 | 当前是数值目标优化，没有分类任务入口 | 适合成功/失败、有无目标结构等标签探索；不等于自动接入可行性约束 |
| 超体积型多目标策略 | GUI 提供 UCB/EHVI/PI 并调用 MultiBgolearn；可设置目标数、模型和 bootstrap | 当前只有 Gryffin+Chimera 按优先级的多目标，Atlas/BoTorch 界面仍限单目标 | 寻找相互竞争性能之间的折衷，而不只是优先满足第一目标 |

源码证据：

1. [数据及候选表导入，main.py L619–663](https://github.com/Bgolearn/BgoFace/blob/133b540f5f73c247f04cba6bb3d1f954aedfc537/src/main.py#L619)。
2. [步长和候选网格，L295–344](https://github.com/Bgolearn/BgoFace/blob/133b540f5f73c247f04cba6bb3d1f954aedfc537/src/main.py#L295)。
3. [单目标模型、采集函数与分类设置，L1208–1268](https://github.com/Bgolearn/BgoFace/blob/133b540f5f73c247f04cba6bb3d1f954aedfc537/src/main.py#L1208)；[实际后端调用，L346–578](https://github.com/Bgolearn/BgoFace/blob/133b540f5f73c247f04cba6bb3d1f954aedfc537/src/main.py#L346)。
4. [分布图，L817–875](https://github.com/Bgolearn/BgoFace/blob/133b540f5f73c247f04cba6bb3d1f954aedfc537/src/main.py#L817)；[LOOCV，L1601–1667](https://github.com/Bgolearn/BgoFace/blob/133b540f5f73c247f04cba6bb3d1f954aedfc537/src/main.py#L1601)；[图像输出，L1088–1164](https://github.com/Bgolearn/BgoFace/blob/133b540f5f73c247f04cba6bb3d1f954aedfc537/src/main.py#L1088)。
5. [多目标设置，L1484–1494](https://github.com/Bgolearn/BgoFace/blob/133b540f5f73c247f04cba6bb3d1f954aedfc537/src/main.py#L1484)；[调用，多目标 L346–367](https://github.com/Bgolearn/BgoFace/blob/133b540f5f73c247f04cba6bb3d1f954aedfc537/src/main.py#L346)。

## 不能直接计入“对方已实现 GUI”的宣传项

官方[网页文档](https://bgolearn.github.io/docs/bgoface.html)还描述联合约束、Pareto 图、超体积跟踪、自动模型选择、Python 代码生成、PDF/PPT 导出等。但在本次核对的最新正式 GUI 核心代码、界面定义和两份官方手册中，没有找到对应的完整控件与调用证据，不能把它们都当作成品已验证能力。

- 约束：找到的是逐变量范围/步长和候选网格，没有总量/配比表达式编辑入口。可以在外部先筛好合法候选表再导入，这与 GUI 原生约束求解不同。
- LOOCV：GUI 图中的模型固定为 GPR（RBF+WhiteKernel），不会随用户选择 RF/SVM/MLP 改变，因此不能称为“已选模型的自动验证比较”。
- 多目标：EHVI 的 GUI 接线存在；没有找到 GUI 的专用 Pareto/超体积演化画布。多目标 max_search 为所有目标共用一个布尔方向。
- 不确定性：底层 MultiBgolearn 确有预测均值/方差与 bootstrap，不能因此声称 GUI 已提供交互式不确定性地图。本轮早期把“预测/不确定性展示”概括得过宽，现以此限定。
- 自动选模型：MultiBgolearn 的 `assign_model=False` 路径会用 LOOCV 比较模型，但 GUI 当前下拉框会传指定模型字符串，不能等价为 GUI 已提供自动模型选择开关。
- 代码生成与 PDF/PPT 报告：文档有声明，本次公开 GUI 源码未核实。普通 PNG 导图与候选 Excel 输出确有代码。
- 自驱实验：分类和批量推荐并不表示已经有机器人、仪器或 LIMS 自动闭环。

## 算法与基准能说明什么

MultiBgolearn 源码确有 GP、RF、GradientBoosting、SVR 及线性模型等路线；非 GP 模型使用 bootstrap 预测分散程度。EHVI 路径根据候选预测分布抽样，再计算非支配前沿与超体积变化；因此不能把对方说成只有简单旧 GP。

证据：[模型与不确定性，funs.py L141、323](https://github.com/Bin-Cao/MultiBgolearn/blob/c960d2623ce10fbedbbfcb677b45f810f41d8e21/src/MultiBgolearn/utility/funs.py#L141)、[采集函数，acquisition.py](https://github.com/Bin-Cao/MultiBgolearn/blob/c960d2623ce10fbedbbfcb677b45f810f41d8e21/src/MultiBgolearn/utility/acquisition.py)。

作者论文 Table 1 和对应基准主要比较随机搜索、Latin hypercube（LHS）与 NSGA-II。统一从 20 个 LHS 初始点开始，每轮 3 点，重复 30 个种子。没有在该表看到 Gryffin、Atlas 或 NaNoBO 同条件对照；论文报告相对这些基线的收益，不能外推成与我们三套引擎的胜负。[作者论文 Table 1 及基准节](https://arxiv.org/html/2601.06820v2)。

此外，同名方法也需要核查实现，不能只按名字比较。MultiBgolearn 当前 qNEHVI 是其自有近似采样/贪心逻辑；公开接口批量路径最终返回首个索引，不能直接等同于 BoTorch 的联合后验 qNEHVI 实现。其 EHVI/PI 最小化选点方向与超体积参考点处理值得另做数值回归，但本轮没有执行验证，不据此判定优化性能。

## 建议 NaNoBO 的补齐顺序

这是产品判断，不是本轮已实现的功能：

1. **先让推荐条件能直接执行**：原单位步长/数值集合、合法候选表、总量/配比等联合约束。总量约束不能简单在推荐后归一化，步长也不能只在推荐后四舍五入，否则会改变搜索空间并制造重复。
2. **让用户看懂推荐**：候选预测均值、不确定性、采集分值及排序导出；同时做与实际引擎一致的验证，不能拿固定 GPR 图冒充所有模型。
3. **开放真正的 Pareto 多目标**：用标准 BoTorch 多目标方法并展示 g、产率、成本等性能的折衷，保留 Chimera 的优先级模式供不同需求选择。
4. **建立同条件基准**：固定搜索空间、初始实验、噪声处理、批量和实验预算，重复多个随机种子；单目标比较达到目标的实验数和最佳值，多目标比较共同参考点下的超体积。先测公开基准，再测与实际材料体系贴近的历史数据/模拟任务。
5. **按实验需求增加分类或描述符**：如果经常记录成功/失败、形貌类别或筛选溶剂/配体，优先级可上调。仪器自动接入另需明确协议。

## Apple 公证说明

Apple 公证是对 Developer ID 签名应用进行自动恶意内容与签名检查，并发放可供 Gatekeeper 验证的票据。它不是算法认证，也不是 App Store 审核。当前 NaNoBO 是本地 ad-hoc 签名并已在本机验证的版本，尚未完成 Developer ID 签名和公证；其他 Mac 从互联网收到它时，可能出现无法验证开发者/安全拦截提示。

来源：[Apple 公证说明](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)、[Apple 安全打开 App 说明](https://support.apple.com/en-us/102445)。这影响分发体验，不会把同一个算法变强或变弱。

