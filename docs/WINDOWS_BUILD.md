# Windows 安装与验收

[简体中文教程](TUTORIAL.zh-CN.md) · [English tutorial](TUTORIAL.en.md) · [Windows 验收说明](WINDOWS_ACCEPTANCE.md)

[Windows Hotfix1 下载与完整验收资料](https://github.com/wei-rui499/NaNoBO/releases/tag/v0.2.3-windows-hotfix1)：推荐普通用户下载名称带 `setup-hotfix1` 的 EXE，安装后直接打开。无需运行下文的维护者命令。

## 使用者安装

Windows Hotfix1 修复了原 0.2.3 测试包中的 Gryffin 与 Atlas 运行错误。使用对应的 `NaNoBO-0.2.3-windows-x64-setup-hotfix1-unsigned.exe`，按中文安装向导完成安装后，从开始菜单打开 NaNoBO。便携版需要完整解压 ZIP 后打开 `NaNoBO/NaNoBO.exe`，保留旁边的 `_internal` 文件夹。

应用自带 Python、CPU 计算库、三个预设引擎、双语教程和练习数据。普通使用者无需安装 Python、Conda、WSL、编译器，不需要 API 账户，也不需要设置环境变量。首次练习可从帮助菜单导出教程数据，再按照中文教程导入、生成建议、补录结果和查看分析。

Gryffin、Atlas 和 BoTorch 是本地运行的真实算法，由用户的实验数据拟合；不是预训练的大语言模型。可选功能由界面按引擎支持范围检查，不能执行的组合会提示用户，不会换成其他模型继续计算。

原 GitHub v0.2.3 附件曾标记为 BUILD ONLY / RUNTIME UNVERIFIED，不能把它当作 Hotfix1。应核对实际文件名及随包验收记录。Hotfix1 的本机验收范围为 Windows 11 Pro x64；Windows 10、ARM64、其他硬件和机构策略未实测。安装器仍未签名，尚不能保证所有电脑首次安装都没有系统信誉提示。

## 修复与验证依据

详见 [Windows 验收说明](WINDOWS_ACCEPTANCE.md)。核心修复包括 Gryffin 对不可用内存统计的日志处理、Olympus 导入循环与非必要可视化依赖的延迟加载、Atlas 日志管道的 UTF-8 编码。

安装验收使用合成数据。除了直接运行便携版实际引擎，还从安装器安装到带中文和空格的目录，运行安装后的模型和 Qt 工作流，检查 CSV/XLS/XLSX、PNG/PDF/SVG 导出以及卸载后项目保留。软件测试不代表实验结果或科研结论得到验证。

## 维护者重建

发布端需要原生 Windows x64、Python 3.10 与 3.13、Microsoft C++ Build Tools 和 Inno Setup 7+。普通使用者不需要这些工具。经典与现代运行时保持隔离，模型公式和上游来源保留。旧 Inno Setup 6 在深目录下复制依赖许可证时会触及 MAX_PATH；新版安装器使用 Inno Setup 7 的扩展路径支持，无需用户修改注册表或挪动文件。

```powershell
$env:PYTHONUTF8 = '1'
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python.exe scripts\bootstrap.py

py -3.13 -m venv .venv-modern
.venv-modern\Scripts\python.exe -m pip install --upgrade pip
.venv-modern\Scripts\python.exe -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
.venv-modern\Scripts\python.exe -m pip install -r requirements-modern.in
.venv-modern\Scripts\python.exe scripts\collect_licenses.py modern
.venv-modern\Scripts\python.exe scripts\build_modern.py

.venv\Scripts\python.exe scripts\build.py --bundle-only
.venv\Scripts\python.exe scripts\fetch_library_sources.py
.venv\Scripts\python.exe scripts\validate_windows_runtime.py --bundle dist/NaNoBO --output validation/windows-portable --fail-fast
.venv\Scripts\python.exe scripts\package_windows.py --compiler 'C:\Program Files\Inno Setup 7\ISCC.exe'
.venv\Scripts\python.exe scripts\validate_windows_installation.py --installer installers/NaNoBO-0.2.3-windows-x64-setup-unsigned.exe --output validation/windows-installation --build-record installers/WINDOWS_BUILD-0.2.3.json
```

`package_windows.py` 只封装和校验文件，不能单独作为运行验收。`validate_windows_runtime.py` 和 `validate_windows_installation.py` 必须成功，才能把构建记录标为已验证。工作流 [windows-release.yml](../.github/workflows/windows-release.yml) 已加入这些门禁，任一模型或安装后界面检查失败便不上传发布产物。工作流修改仍须提交后在 GitHub 上实际运行；文件存在不等于远程构建已经通过。

本次本机 Hotfix1 从已校验 SHA-256 的官方便携版保留原生科学库，使用同版本 CPython 3.10 重新编译六个修复模块，并逐项核对冻结模块。工具是 `scripts/repack_windows_hotfix.py`，来源及修复源码摘要记录在 `WINDOWS_HOTFIX.json`。它不需要普通用户运行。长期发布应使用以上完整源码重建流程。

## 来源与许可

原作者、方法和引用见 [公开致谢](../ACKNOWLEDGMENTS.md)、[如何引用](HOW_TO_CITE.md) 和 [第三方说明](../THIRD_PARTY_NOTICES.md)。上游修改见 [修改记录](UPSTREAM_MODIFICATIONS.md)。安装器包含第三方许可证；适用的第三方对应源码与原官方 Windows 发布附件配套保留。
