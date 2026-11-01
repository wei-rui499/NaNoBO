# 开发与重建

最终用户下载适合自己电脑的安装包；这些命令给开发者和发布维护者。各平台必须使用相应原生构建机。Mac 本机验证；Windows 仅同步原生构建，由使用者在 Windows 电脑验证运行效果。

## 两套隔离环境

Gryffin/Atlas 的兼容运行时使用 Python 3.10；现代 BoTorch 工作流使用 Python 3.13。先在仓库根目录准备两个相应解释器，创建 `.venv` 和 `.venv-modern`。安装命令会联网获取固定版本；不需要把本地虚拟环境提交 Git。

```sh
python3.10 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python scripts/bootstrap.py
python3.13 -m venv .venv-modern
.venv-modern/bin/python -m pip install --upgrade pip
.venv-modern/bin/python -m pip install -r requirements-modern.in
```

`bootstrap.py` 固定上游提交、保留来源和许可、从 Gryffin 未修改的 `.pyx` 重生成兼容 C 扩展，并应用已标记的兼容补丁。BoTorch 和经典运行时不应混用 Torch/Python 动态库。

## 运行及回归

```sh
PYTHONPATH=src .venv/bin/python -m chembo
CHEMBO_INTEGRATION=1 QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_app.py tests/test_app_v2.py tests/test_workflow_regressions.py tests/test_engine.py tests/test_space.py tests/test_io.py tests/test_analysis_view.py tests/test_publication.py tests/test_tutorial_help.py tests/test_tutorial_examples.py tests/test_windows_packaging.py -q --junitxml=validation/regression-0.2.3.xml
PYTHONPATH=src .venv-modern/bin/python -m unittest discover -s tests -p 'test_mod*.py' -v
```

模型测试使用合成数据，不调用真实仪器。

## 构建应用目录

```sh
.venv-modern/bin/python scripts/collect_licenses.py modern
.venv-modern/bin/python scripts/build_modern.py
.venv/bin/python scripts/build.py --bundle-only
```

现代 worker 必须在主程序构建完成后整体复制，保留自己的 `_internal` 和库搜索路径。构建脚本处理这一点。`dist/NaNoBO.app` 是待最终封装的本地应用目录；这里只承诺构建目录流程，不将历史测试报告冒认为新机器的验证结果。

## 模拟实验与 DMG 发布

`scripts/run_simulated_lab.py` 支持在指定输出目录生成可复现的模拟实验、图表和项目：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/run_simulated_lab.py --output validation/repeated-run --bundle dist/NaNoBO.app
```

`scripts/package_macos.py` 从 `chembo.__version__` 读取当前版本（本次为 0.2.3），作为发布者封装脚本，会再次签名并验证原生模型、界面和导图。它需要当前机器重新生成的验收资料，按本次目录约定包括：

- `validation/regression-0.2.3.xml`：JUnit 回归结果，不能含失败。
- `docs/VALIDATION_V0.2.3.json`：本次运行生成的证据。仓库内保留的是经脱敏的历史参考，重发布前应重新生成。
- `release/NaNoBO-0.2.3-tutorial-examples.zip`：配套合成教学文件。
- `release/library-sources/`：与实际二进制一致的 LGPL 等对应库源码和校验表；可用 `scripts/fetch_library_sources.py` 准备。

新的克隆不会自动具有这些发布资料。先执行 `--bundle-only`、完成当前版本验证并准备这些附件，再调用封装脚本。修改版本号时同步更新 pyproject、chembo.__version__、构建/封装和源归档版本；旧版本证据保留为历史记录。

安装包、应用源码包、第三方声明、对应库源码与验证附件在同一 GitHub Release 提供。未公证测试版应如实标注；公证不等于上架 App Store，也不是发布本开源源码的前提。

## 更新教程与练习

修改 README.md / README.en.md 和 docs/TUTORIAL.zh-CN.md / docs/TUTORIAL.en.md 后运行 `scripts/render_guides.py`。构建脚本会自动渲染带目录、语言选择和本地图表的离线教程。练习数据随包保留；用户从“帮助 → 导出教程练习数据…”得到可写副本，再次导出不会覆盖已有文件。

重新生成 Excel 教学文件时，开发环境额外安装 `xlwt==1.3.0` 后运行 `scripts/generate_tutorial_examples.py`；xlwt 仅用于生成旧版 XLS，不属于应用运行依赖。`PYTHONPATH=src .venv-modern/bin/python scripts/validate_tutorial_models.py` 使用实际模型重放四条练习。Windows 工作流只构建、检查封装文件与压缩包完整性，不启动程序或测试。
