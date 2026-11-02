# Windows Hotfix1 验收说明

[下载 Windows Hotfix1](https://github.com/wei-rui499/NaNoBO/releases/tag/v0.2.3-windows-hotfix1) · [机器可读验收摘要](WINDOWS_ACCEPTANCE-hotfix1.json)

本次只验证 Windows。基线为 GitHub v0.2.3，提交 `9d0b2d6ead88282a0cc774200c957d3016e2e9d1`。基线便携包 SHA-256 为 `461cf348b3dc49da82646a59df90045cd464913c2cfea24883204a9364fc6825`。所有输入均为合成数据，实际模型由应用自带的 EXE 执行。

## 原版问题与根因

原版 Windows 原生模型验收 39 项中仅 32 项通过：Gryffin 四项、Atlas 三项失败。安装成功、文件齐全和 BoTorch 可运行不足以证明整个软件开箱即用。

| 问题 | 实际原因 | 修复 |
| --- | --- | --- |
| Gryffin 完成计算后报错 | Windows 无 Unix resource，统计函数返回 None，但 build_surrogate 与 recommend 的汇总日志仍以数值格式化 | 两条真实路径都在统计不可用时输出 unavailable，不改变模型计算 |
| Gryffin 有限整数域推荐越界 | 扰动采样使用零起始的选项编号，但按用户的原始整数上下限裁剪 | 整数扰动按 0 到 high-low 裁剪；连续变量仍使用原始上下限 |
| Atlas 无法导入 | Dataset 加载 ParameterSpace 时提前导入 Campaign，Campaign 和 data_transformer 又导入尚未初始化的 Dataset | campaigns 包延迟导出 Campaign，保留原公开类名 |
| Atlas 中文 Windows 管道报错 | 欢迎日志含 GBK 不能编码的 Unicode 字符，计算进程因此异常退出 | worker 启动时将 stdout/stderr 配置为 UTF-8，并处理无控制台情况 |
| Atlas 单条连续推荐返回已测点 | 上游梯度优化未识别 KnownConstraints 容器，最终优化未执行已测/待办排除 | 统一预设为 Atlas 原生 Pymoo 采集优化器；保留相同 GP 与采集函数 |
| Atlas 成功仍要求安装 seaborn | Olympus 顶层提前加载未使用的 Plotter 和基准运行器 | 延迟加载两项可选接口；NaNoBO 自带绘图不需要 seaborn |
| 自定义深目录安装失败 | Inno Setup 6 在复制长路径依赖许可证时 MoveFile 失败并回滚 | 安装器改用支持扩展路径的 Inno Setup 7；保留全部许可证，不要求用户改系统设置 |

修复均保留在 bootstrap 重建流程中。新增回归测试覆盖内存日志的两条路径、延迟导出及缓存、补丁幂等、GBK 流输入的 UTF-8 输出。

## 验收内容

`scripts/validate_windows_runtime.py` 通过实际冻结工作进程覆盖三个引擎的已有数据训练、无数据初始设计、类别与整数混合变量、批量推荐、教程四类工作流、待办排除和补录、留一验证、多目标、分类、约束、复现与数据敏感性，以及非法输入和不支持组合的拒绝。成功案例不允许隐藏缺失模块报错，也不允许用其他模型顶替。

`scripts/validate_windows_installation.py` 安装到中文与空格路径后，清除开发用环境变量，并只保留系统 PATH。再次运行实际模型，再运行 Qt 界面到工作进程的交接、表格导入及图表导出，最后卸载并核对项目文件保留。测试控制器使用外部 Python 收集结果；用户程序的计算依赖全部来自安装目录。

此前人工界面验收还检查了项目保存重开、待办导出与补录、CSV/Excel 导入、留一图、分类概率和混淆矩阵、三目标 Pareto、预测表和图表导出、计算取消与数据保留、离线教程。

本次本机实际系统为 Windows 11 Pro x64 10.0.26200。具体最终通过数、安装器和 ZIP 的 SHA-256、原始测试记录位置见交付目录中的 `WINDOWS_ACCEPTANCE-hotfix1.md` 与 `WINDOWS_ACCEPTANCE-hotfix1.json`。早期失败及中间构建记录保留在 validation/，不能冒充最终包的验收证据。

## 交付范围

三个选项是真实 Gryffin、Atlas 与 BoTorch 的预设算法配置，由用户实验数据拟合。用户不需要安装 Python、设置环境或申请 API 账户。安装器未签名；Windows 10、ARM64、其他电脑及安全策略尚未实测。此处不承诺所有 Windows 电脑无提示安装，也不代表湿实验性能得到验证。

修复版发布在 [Windows Hotfix1](https://github.com/wei-rui499/NaNoBO/releases/tag/v0.2.3-windows-hotfix1)，该页提供安装器、便携版、对应源码、脱敏验收资料和 SHA-256。原 v0.2.3 的 Windows 附件保留作历史基线，日常使用请下载 Hotfix1。

Windows 源码重建配置已加入运行验收门禁。本次已验收安装包的本机测试记录与后续 GitHub Actions 源码重建是独立记录；远程构建状态以 Actions 实际结果为准。
