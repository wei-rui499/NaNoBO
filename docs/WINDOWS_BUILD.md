# Windows 原生安装包

目标用户安装 `.exe` 后即可使用图形界面，无需安装 WSL、Ubuntu、Python、Conda、Docker、编译器或显卡驱动。发布端负责携带 Python、Gryffin 的原生扩展及计算依赖。CPU 版即可进行优化。

截至 2026-10-31，本工作区的执行机器是 Apple Silicon Mac；Windows 构建、安装和卸载流程已经写入原生 CI，但尚未在此会话中运行。`build.yml` 文件存在不代表 Windows 安装包已经构建成功。只有工作流通过并产生安装器，且在目标 Windows 机器上完成界面验收，才能标记 Windows 版已验证。

## 从 GitHub 生成安装器

1. 将项目作为独立仓库上传；先检查根目录及 `research/license_audit.md` 的许可要求。构建不会替你公开仓库或创建 Release。
2. 在 GitHub 仓库的 **Actions → Native desktop installers → Run workflow** 启动构建。默认只运行 Windows；勾选 `include_macos` 可同时构建 Apple Silicon Mac 版。
3. 工作流在 `windows-2022` x64 原生 Windows runner 上安装依赖、编译扩展、运行真实模型测试、打包应用，并用 Inno Setup 生成每用户安装器。
4. 构建会先清除子进程的 Python 环境变量并缩减 PATH，验证独立现代引擎的初始设计、待实验续接与实测数据建模；再检查打包目录中的三个引擎，静默安装到临时目录，检查安装后引擎，最后卸载。任一检查失败则不进入上传步骤。
5. 全部通过后，从工作流的 **Artifacts** 下载 `NaNoBO-windows-x64-unsigned`。其中的 `NaNoBO-0.1.0-windows-x64-setup-unsigned.exe` 才是分发给使用者的安装器。Artifacts 默认保留 14 天。

工作流只保存构建产物，不自动发布 GitHub Release。Windows 与 Mac 各自在本机系统构建；PyInstaller 不是跨操作系统编译器。

## 本机 Windows 构建（给维护者）

维护者需要原生 Windows 10/11 x64、Python 3.10 与 3.13、Microsoft C++ Build Tools（含 Windows SDK）及 Inno Setup 6。最终使用者不需要这些工具。以下命令在项目根目录的 PowerShell 执行。

```powershell
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python.exe scripts\bootstrap.py

py -3.13 -m venv .venv-modern
.venv-modern\Scripts\python.exe -m pip install --upgrade pip
.venv-modern\Scripts\python.exe -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
.venv-modern\Scripts\python.exe -m pip install -r requirements-modern.in

$env:PYTHONPATH = (Join-Path $PWD 'src')
$env:CHEMBO_INTEGRATION = '1'
$env:QT_QPA_PLATFORM = 'offscreen'
$env:MPLBACKEND = 'Agg'
.venv-modern\Scripts\python.exe -m unittest discover -s tests -p test_modern.py -v
.venv-modern\Scripts\python.exe scripts\collect_licenses.py modern
.venv-modern\Scripts\python.exe scripts\build_modern.py
$env:CHEMBO_MODERN_WORKER = (Resolve-Path 'dist-modern/chembo-modern-worker/chembo-modern-worker.exe').Path
.venv-modern\Scripts\python.exe -m unittest discover -s tests -p test_modern.py -v
.venv\Scripts\python.exe -m pytest tests/test_engine.py tests/test_app.py -q
.venv\Scripts\python.exe scripts\build.py
.venv\Scripts\python.exe scripts\smoke_frozen.py --bundle 'dist/NaNoBO'
& 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' scripts\build_installer.iss
```

输入的 Python 小版本可能影响可用轮子；以通过 CI 的实际版本和产物中的 `windows-*-resolved.txt` 为准。Mac 的依赖锁文件只记录 Mac 上的解析结果，不能作为 Windows 完整轮子验证的替代。

## 安装与使用验收

发布前在一台未安装 Python/WSL/Conda 的 Windows 机器上执行：

1. 断开网络，双击安装器，使用普通用户安装，检查开始菜单启动和可选桌面快捷方式。
2. 在教学示例中分别选择 Gryffin、Atlas、BO-MCP，生成结果并确认界面保持响应；检查初始设计与有观测数据的模型推荐均能工作。
3. 新建含中文名称的项目，导入 CSV、导出下一批，填写目标值后重新导入，保存并关闭。重新启动后打开项目，确认实测及待实验记录保留。
4. 检查错误数据提示、取消计算、关闭前未保存提示。
5. 从 Windows 设置卸载程序；保存到安装目录以外的实验项目和 CSV 应保留。

CI 的引擎检查不替代上述交互验收，也不替代机构终端策略验证。GitHub Windows runner 的账号本身有管理员权限；安装器不请求提升权限，并不等于已在受限的标准用户账号下完成验证。

## 当前兼容边界

- **Windows x64**：目标为原生 CPU 应用；尚待首次原生构建及交互验收。Windows ARM64 运行 x64 版不在本次已验证范围。
- **Apple Silicon Mac**：另行构建原生 arm64 版本。
- **Intel Mac**：当前完整三引擎包不支持。PyTorch 官方已停止供应较新版本的 macOS x86_64 轮子；需要另外维护老依赖版或自行构建运行库，不能把 arm64 包标为通用版。
- **签名**：当前安装器为 unsigned。公开分发前若需要减少系统信誉提示，可由发布者配置 Windows 代码签名；这与算法运行是否需要 WSL 是不同问题。不要要求用户关闭 Defender 或系统安全策略。
- **包体积**：应用携带两套隔离的科学计算运行时，完整版体积较大；这用于将依赖配置从使用者转移到发布端。当前不要求 CUDA 或 GPU。

## 源码审查结论

固定 Gryffin 源码未发现活动 `.py/.pyx` 路径使用 `unistd`、POSIX shell 或强制 WSL。C 扩展使用 NumPy/Cython 与 `libc.math`。仓库附带的旧生成 C 文件需要用当前 Cython 重新生成，然后在目标系统编译。

应用将 Gryffin 设置为 `num_cpus=1`，避开上游 `acquisition`、`sample_selector`、`category_reshaper` 的多进程分支，计算本身由应用工作子进程执行。`utilities/decorators.py` 定义的 `processify` 闭包未在当前固定源码中被使用；以后升级上游或开启多进程时仍需检查 Windows spawn 和序列化。主入口使用 `multiprocessing.freeze_support()`。这些是静态适配依据，不构成 Windows 成功运行的证据。

## 官方技术依据

- [PyInstaller 打包原理及目标系统要求](https://pyinstaller.org/en/stable/operating-mode.html)：包含 Python 解释器；需要在目标操作系统打包。
- [Inno Setup 普通用户安装](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm)：本安装器采用 `PrivilegesRequired=lowest`，安装到用户程序目录。
- [GitHub 原生托管 runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)：工作流使用 Windows x64 和可选 Mac arm64 runner。
- [PyTorch 官方关于 Intel Mac 轮子停止供应的说明](https://github.com/pytorch/pytorch/issues/127870)。
- [PyTorch CPU 版安装源](https://pytorch.org/get-started/previous-versions/)。
