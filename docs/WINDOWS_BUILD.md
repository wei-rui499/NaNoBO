# Windows 原生安装包与构建说明

[简体中文教程](TUTORIAL.zh-CN.md) · [English tutorial](TUTORIAL.en.md) · [下载页](https://github.com/wei-rui499/NaNoBO/releases)

## 给使用者：下载哪个文件

Windows 版使用与 Mac 相同的应用源码、模型适配、双语教程和练习数据，直接在原生 Windows 上运行。使用者无需安装 WSL、Ubuntu、Python、Conda、Docker 或编译器，也不要求 GPU。

| 文件 | 用途 |
| --- | --- |
| `NaNoBO-0.2.3-windows-x64-setup-unsigned.exe` | 普通用户安装器；安装到自己的用户目录，可建立开始菜单和桌面快捷方式 |
| `NaNoBO-0.2.3-windows-x64-portable-unsigned.zip` | 便携版；完整解压后打开 `NaNoBO/NaNoBO.exe`，保留旁边的 `_internal` 文件夹 |
| `WINDOWS_BUILD-0.2.3.json` | 构建记录、文件清单、依赖版本及本次验证边界 |
| `SHA256SUMS-windows-0.2.3.txt` | 下载文件的 SHA-256 校验值 |
| `NaNoBO-0.2.3-windows-source.zip` | 该 Windows 构建对应的应用与适配源码 |
| `NaNoBO-0.2.3-windows-library-sources.zip` | 适用第三方依赖的对应版本源码和校验记录 |

安装后，从帮助菜单打开“中文使用教程”或“English tutorial”，通过“导出教程练习数据…”把练习文件复制到自己的实验文件夹。教程、练习数据和计算引擎均随程序安装，日常使用不需网络或 API 账户。

本次按使用者要求，**只在 Windows 编译和封装，不启动应用，不进行模型、GUI、安装／卸载功能测试**。下载页和构建记录标为 **BUILD ONLY / RUNTIME UNVERIFIED**，Windows 实际运行由使用者自行验收。Mac 的功能验收不作为 Windows 已验证的证据。

安装器目前未进行代码签名；若受机构终端策略限制，按所在机构的软件安装流程处理。Windows ARM64 上运行 x64 程序未纳入本次兼容声明。当前目标为 Windows 10/11 x64；较老系统或受限环境的运行情况待实际反馈。

## GitHub 如何构建并保存 Windows 版本

工作流文件是 [`.github/workflows/windows-release.yml`](../.github/workflows/windows-release.yml)，名称为 **Windows native installer (build only)**。

1. `main` 有新提交时自动构建，也可在仓库 **Actions → Windows native installer (build only) → Run workflow** 手动启动。
2. 在原生 `windows-2022` x64 runner 上建立 Python 3.10 经典环境和 Python 3.13 现代环境。Gryffin 的两个 Cython 扩展由目标系统的 Microsoft C++ 工具链编译，PyTorch 从官方 CPU 轮子源安装。
3. 分别用 PyInstaller 封装现代工作进程与桌面应用；两套 Python 运行时保持隔离，避免 DLL 或模型依赖版本混用。随后把同一份离线教程和练习文件放入应用。
4. 仅检查打包目录中所需的 EXE、DLL、C 扩展、Qt 插件、许可证、双语教程和至少四个练习项目是否存在；生成 Inno Setup 安装器和便携 ZIP，校验 ZIP CRC 与文件 SHA-256。**不执行应用或安装器。**
5. 构建产物保存在 `NaNoBO-0.2.3-windows-x64-build-only` Artifact 中，保留 14 天。只有上一步成功才进入产物上传和 Release 附件步骤。
6. 发布步骤只新建或复用对应源码提交的 **Draft / Pre-release**，附加 Windows 文件，绝不自动把草稿公开，也不覆盖已经公开的同版本 Release。维护者完成本次发布整理后统一公开。若已有标签，必须指向本次构建的提交。

工作流启动、排队或配置文件存在，都不代表 EXE 已经构建成功；以 Actions 的最终状态和实际下载附件为准。构建完成也不代表 Windows 应用功能已验证。

## 维护者在 Windows 本机重建

需要原生 Windows x64、Python 3.10 和 3.13、Microsoft C++ Build Tools（含 Windows SDK），以及 Inno Setup 6.5+。这些是发布端工具，最终使用者不需要安装。以下命令在仓库根目录的 PowerShell 中执行：

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
.venv\Scripts\python.exe scripts\package_windows.py --compiler 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
```

产物位于 `installers/`。`package_windows.py` 只编译、封装和检查文件完整性；不会启动应用、worker 或安装器。Mac 的锁文件包含 Mac 平台解析结果，不能直接作为 Windows 全量依赖锁使用；本次实际 Windows 依赖版本会写入 `WINDOWS_BUILD-*.json`。

经典环境保留 Gryffin 所需的 NumPy 1.23.5。DEAP 的 moocore 依赖在 Windows 固定为支持该 NumPy 版本的 0.1.10，下载脚本按实际安装版本附带对应源码；不把 Mac 环境中已有的 0.3.2 对应源码冒充为 Windows 版本。Gryffin 的 Cython 代码在临时文件中重生成后原子替换，既保留修改声明，也允许从已带声明的源码快照再次构建。

## 使用者自行测试时如何反馈

建议先用教程的合成练习，保存文件到安装目录以外的工作文件夹。反馈时说明 Windows 版本、NaNoBO 版本、所用教程步骤、弹窗内容和最小可复现的合成项目。请先移除真实实验数据、个人目录与其他敏感信息。若问题涉及计算，在界面保留的日志中定位报错；不要为了运行程序关闭系统防护。

原有 `scripts/smoke_frozen.py` 和 `--verify-ui` 是可选维护工具，本次 Windows 工作流没有调用。源码中保留这些工具不表示本次 Windows 已经运行过这些检查。

## 科研来源与许可

Gryffin、Atlas、BoTorch、scikit-learn 等原始方法的作者署名见 [公开致谢](../ACKNOWLEDGMENTS.md)；按实际使用的方法引用，见 [如何引用](HOW_TO_CITE.md)。完整许可证、修改说明及适用依赖的对应源码随应用或 Release 提供，见 [第三方说明](../THIRD_PARTY_NOTICES.md)。教程或安装包不会改变上游算法归属。

技术依据：[PyInstaller 目标系统构建要求](https://pyinstaller.org/en/stable/operating-mode.html)、[Windows DLL 搜索路径](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html)、[Inno Setup 普通用户安装](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm)、[GitHub Windows runner 软件清单](https://github.com/actions/runner-images/blob/main/images/windows/Windows2022-Readme.md)。
