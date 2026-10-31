# 开发与重建

最终用户直接下载 DMG；这些命令给开发者和发布维护者。各平台必须使用相应原生构建机；本次已经验证 macOS arm64，Windows 暂缓。

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
CHEMBO_INTEGRATION=1 QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_app.py tests/test_app_v2.py tests/test_workflow_regressions.py tests/test_engine.py tests/test_space.py tests/test_io.py tests/test_analysis_view.py -q --junitxml=validation/simulated-lab-20261031/regression-classic.xml
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

当前 `scripts/package_macos.py` 是 0.2.1 发布者封装脚本，会再次签名并验证原生模型、界面和导图。它需要当前机器重新生成的验收资料，按本次目录约定包括：

- `validation/simulated-lab-20261031/regression-classic.xml`：JUnit 回归结果，不能含失败。
- `docs/VALIDATION_V0.2.1.json`：本次运行生成的证据。仓库内保留的是经脱敏的历史参考，重发布前应重新生成。
- `release/NaNoBO-0.2.1-simulated-validation.zip`：带合成来源声明的完整模拟资料。
- `release/library-sources/`：与实际二进制一致的 LGPL 等对应库源码和校验表；可用 `scripts/fetch_library_sources.py` 准备。

新的克隆不会自动具有这些发布资料。先执行 `--bundle-only`、完成当前版本验证并准备这些附件，再调用封装脚本。修改版本号时同步更新 pyproject、chembo.__version__、构建/封装和源归档版本；旧版本证据保留为历史记录。

安装包、应用源码包、第三方声明、对应库源码与验证附件在同一 GitHub Release 提供。未公证测试版应如实标注；公证不等于上架 App Store，也不是发布本开源源码的前提。
