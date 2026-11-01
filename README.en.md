[简体中文](README.md) | [English](README.en.md)

# NaNoBO

**Turn the experiments you have already run into a useful next batch.**

NaNoBO is a desktop experiment-planning tool for chemists. Describe what you can vary, enter the results you have measured, and ask for the next conditions to try. After running that batch, add the measurements and repeat.

For example: which temperature and additive should you try next to improve yield? Which volume ratios are allowed when total volume is fixed? What are the trade-offs between yield and cost? If your result is a shape label such as “aggregated”, “spherical” or “rod-like”, which experiment would help clarify the boundary between classes?

**The installer runs locally and includes its computing environment. You do not need Python, WSL, Docker or a model API account.** The application interface is currently in Chinese. Both this page and the detailed tutorial are available in English; the tutorial includes the exact Chinese button labels so you can follow along.

[Download installers](https://github.com/wei-rui499/NaNoBO/releases) · [Start with the practice data](docs/TUTORIAL.en.md) · [中文教程](docs/TUTORIAL.zh-CN.md)

![NaNoBO desktop: experiment settings, completed experiments, next batch and model analysis](docs/screenshots/NaNoBO-preview.png)

## Your first ten minutes

Start with the supplied **synthetic teaching data**. You do not need to study the algorithm first.

1. Download the appropriate installer and the tutorial data bundle from [Releases](https://github.com/wei-rui499/NaNoBO/releases). The Help menu in version 0.2.2 and later also provides the tutorials and practice data.
2. Open `01_quickstart/project.chembo.json`. The project already defines temperature, cycle count and additive, and contains **6 synthetic measurements**.
3. Click **Generate next batch** (`生成下一批实验 →`). You should see **2 pending conditions** in `下一批 / 待实验`.
4. Choose **Export CSV for results** (`导出待回填 CSV`). Find those exact conditions in `all-simulated-results.csv`, copy the corresponding synthetic yield values into your exported sheet, and import it through `已完成实验 → 导入 Excel / CSV`.
5. Save the project, then click **Analysis and cross-validation** (`分析与交叉验证`) to inspect predictions, measured-versus-predicted plots and errors before planning another batch.

[Follow the detailed walkthrough and check the expected results at each step →](docs/TUTORIAL.en.md#3-ten-minute-exercise-temperature-additive-and-yield)

These numbers teach the software workflow; they are not real chemistry recipes or experimental evidence. `all-simulated-results.csv` is a lookup table for this exercise. Do not import the entire file: doing so would mark every candidate as already measured.

## Download and install

| Computer | Installation and release status |
| --- | --- |
| Apple Silicon Mac, macOS 14+ | Download `macOS-arm64.dmg` from Releases, open it and drag NaNoBO into Applications. An installation build has completed synthetic workflow validation. |
| Windows 10/11, x64 | Code, tutorials and packaging are synchronized with Mac. Use the `windows-x64-setup-unsigned.exe` actually provided in Releases. **Windows runtime validation is pending**; see the [Windows build guide](docs/WINDOWS_BUILD.md). |
| Intel Mac / Windows ARM64 | A corresponding validated installer is not currently available. |

The Mac research preview is not Apple-notarized. If macOS blocks the first launch, follow [Apple's instructions](https://support.apple.com/en-us/102445) to review it in Privacy & Security. An unsigned Windows preview may also trigger a reputation warning; do not disable system security protection. See the [installation walkthrough](docs/TUTORIAL.en.md#1-install-and-open-the-application).

The installed app includes its dependencies. The development guides below are for maintainers rebuilding the software; end users do not need to run those commands.

## What can I do with it?

| Your experimental question | What to do in NaNoBO | Practice project |
| --- | --- | --- |
| Improve yield, selectivity or signal, or reduce a size error | Define one numerical objective, choose maximize or minimize, and add measurements after each batch | [01: Temperature, additive and yield](examples/tutorial/01_quickstart/) |
| Work with dispensing increments, a fixed total volume or allowed ratios | Set steps, total/linear rules and ratio limits, or import an explicit table of feasible recipes | [02: Fixed-total recipes](examples/tutorial/02_recipe/) |
| Balance yield against cost | Use Pareto optimization to inspect trade-offs rather than collapsing everything into one score | [03: Multiple objectives](examples/tutorial/03_pareto/) |
| Learn success/failure or morphology labels | Use classification active learning to inspect class probabilities and uncertain boundaries | [04: Morphology classes](examples/tutorial/04_classification/) |
| Reuse an existing Excel results sheet | Import `.xls`, `.xlsx` or UTF-8 `.csv`; select the results worksheet when prompted | [Import and refill](docs/TUTORIAL.en.md#6-import-export-and-refill-experimental-results) |
| Understand a recommendation and check the model | Inspect predicted values, model uncertainty and candidate scores, then run same-model leave-one-out validation | [Predictions and plots](docs/TUTORIAL.en.md#10-model-checks-and-every-chart) |
| Prepare a group-meeting or manuscript figure | Export the current plot as PNG/PDF/SVG and export predictions or measurements as CSV | [Export and archive](docs/TUTORIAL.en.md#11-save-export-and-archive) |

## Which engine should I choose?

For a first session, follow the tutorial with **BoTorch · 优化与分类**. This workflow includes recipe restrictions, Pareto analysis, classification and the current model-diagnostic panels.

| Name in the app | Current supported workflow |
| --- | --- |
| **BoTorch · 优化与分类** | Single-objective optimization, steps/candidate tables/joint constraints, Pareto, classification and model analysis. Model settings are fixed; follow the workflow. |
| **Gryffin · 类别与连续变量** | Native Gryffin recommendations. Multiple numerical objectives can be handled in table order as priorities using Chimera. |
| **Atlas · 高斯过程** | Native Atlas GPPlanner for single-objective and batch recommendations. |

Native Gryffin and Atlas recommendations are not accompanied by predictions or validation from a substitute model. A feature of an upstream framework is not automatically a feature exposed by this desktop app; see the [engine guide](docs/TUTORIAL.en.md#7-engines-and-priority-objectives).

A recommendation is a suggestion for an experiment. A prediction is a model estimate. Only an actual measurement becomes experimental evidence. Classification explores uncertain class boundaries; it does not necessarily prioritize the condition most likely to succeed.

## Tutorials, practice files and validation

- [Full English tutorial](docs/TUTORIAL.en.md) / [中文完整教程](docs/TUTORIAL.zh-CN.md): installation, each control, plots and troubleshooting.
- [Practice files](examples/tutorial/): four complete projects, empty projects, refill exercises and equivalent CSV/XLS/XLSX result tables. All data are explicitly synthetic.
- [Features and data format](docs/V0.2_FEATURES.md): detailed limits and fields, currently in Chinese.
- [Software validation](docs/VALIDATION.md): completed checks and their scope. Synthetic experiments check software behavior; performance on a real system needs real experiments.
- [Development and rebuilding](docs/DEVELOPMENT.md) / [Windows builds](docs/WINDOWS_BUILD.md): for developers and maintainers, currently in Chinese.

## Scientific acknowledgments, licenses and citation

NaNoBO provides the desktop interface, experiment records and result refill, feasible recipe domains, analysis plots and installer integration. **Gryffin, Phoenics, Chimera, Atlas, Olympus, BoTorch, GPyTorch, scikit-learn and the underlying research methods belong to their respective authors and teams.** Retained BO-MCP compatibility code also keeps its original attribution. NaNoBO is an independent project.

When publishing research that uses this software, cite NaNoBO and **the methods you actually used**: [acknowledgments](ACKNOWLEDGMENTS.md) · [citation guide](docs/HOW_TO_CITE.md) · [14 research and software references](REFERENCES.bib) · [CITATION.cff](CITATION.cff).

NaNoBO's own code uses [Apache-2.0](LICENSE). Upstream code, Qt and other dependencies retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md), [distribution details](docs/THIRD_PARTY.md) and [upstream modifications](docs/UPSTREAM_MODIFICATIONS.md).
