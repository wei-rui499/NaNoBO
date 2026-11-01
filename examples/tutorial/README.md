# NaNoBO 教程练习数据 / Tutorial exercises

**全部为 SYNTHETIC 模拟数据，不是真实化学实验，也不是合成建议。**

在应用中选择“帮助 → 中文使用教程 / English tutorial”，按练习逐步操作。请先复制本文件夹到自己的工作位置，不修改安装目录中的原件。

| 文件夹 | 内容 | 初始已完成 | 初始待实验 | 全部合法候选 |
| --- | --- | --- | --- | --- |
| 01_quickstart | 单目标、连续／整数／类别变量 | 6 | 0 | 20 |
| 02_recipe | 步长、固定总量、配比、候选清单 | 6 | 0 | 21 |
| 03_pareto | 产率与成本折衷，另附三目标例子 | 6 | 0 | 28 |
| 04_classification | 三种形貌，另附成功／失败例子 | 6 | 0 | 28 |

打开每个文件夹的 `project.chembo.json`，直接分析或推荐。要练习导入，改为打开 `empty-project.chembo.json`，然后只导入一种 `seed-observations.csv/.xlsx/.xls`；它们是同一份数据，不要重复导入。Excel 选择 **Results** 工作表。

要做完全固定的回填练习：打开 `pending-practice.chembo.json`，导入对应 `followup-results.csv`，应从 **6 个已完成／2 个待实验**变为 **8 个已完成／0 个待实验**。

自己刚生成的建议可能不同：导出待回填 CSV，按全部变量在 `all-simulated-results.csv` 找到完全相同的条件，填入对应模拟结果再导入。**不要把整张答案表当作一批新实验导入，也不要用固定 followup 去回填不匹配的新建议。**

`candidates.csv` 只含变量，使用“配方约束 / 候选表…”导入。它不是实验结果表。每个文件夹的 `README.txt` 有英文简要说明；`manifest.json` 提供可核对的数量。

## English

All data are **SYNTHETIC**, generated for learning software workflows. Open **Help → English tutorial** in NaNoBO for the full guide.

- Open `project.chembo.json` to begin with six measured rows and no pending experiments.
- Open `empty-project.chembo.json` to practise importing ONE seed file; CSV, XLSX and XLS contain the same rows. Choose the **Results** worksheet.
- Open `pending-practice.chembo.json`, then import its matching `followup-results.csv`: **6 completed / 2 pending → 8 completed / 0 pending**.
- For freshly generated recommendations, look up the EXACT variable combination in `all-simulated-results.csv` and fill the exported pending CSV. Do not import the whole answer table.
- `candidates.csv` contains allowed conditions only. Import it through the recipe/candidate dialog, not the observation import button.
- The Pareto folder also provides a ready three-objective project; the classification folder also provides a binary success/failure project, with separate answer tables.
