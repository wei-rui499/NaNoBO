# Third-party notices / 第三方归属声明

NaNoBO 的自有代码采用根目录 [Apache License 2.0](LICENSE)。该根许可证只适用于 NaNoBO 自有贡献；上游代码、随包动态库、字体和其他依赖继续受各自的许可证与版权声明约束。

本文件是可读索引，**不取代完整许可正文**。源码与安装包需同时保留 `licenses/` 中适用的许可证、NOTICE/COPYRIGHT、版本清单以及本文指向的修改记录和对应源码。

## 主要模型与软件来源

| 项目 | 保留的原始归属 | 许可与本地正文 |
| --- | --- | --- |
| Gryffin | Copyright (C) 2020 Harvard University；完整作者与源码内声明按原件保留 | Apache-2.0；[`licenses/upstream/Gryffin-Apache-2.0.txt`](licenses/upstream/Gryffin-Apache-2.0.txt) |
| Atlas | Copyright (c) 2022 rileyhickman | MIT；[`licenses/upstream/Atlas-MIT.txt`](licenses/upstream/Atlas-MIT.txt) |
| Olympus | Copyright (c) 2020 Aspuru-Guzik group repo | MIT；[`licenses/upstream/Olympus-MIT.txt`](licenses/upstream/Olympus-MIT.txt) |
| Chimera / matter-chimera 1.0 | Copyright (c) 2021 Aspuru-Guzik Group | MIT；`licenses/classic/matter-chimera/` 中的 LICENSE |
| Golem / matter-golem 1.0 | Copyright (c) 2021 Aspuru-Guzik group repo | MIT；`licenses/classic/matter-golem/` 中的 LICENSE |
| BO-MCP / bo-engine | Copyright (c) 2026 Willi Gottstein | MIT；[`licenses/upstream/BO-MCP-MIT.txt`](licenses/upstream/BO-MCP-MIT.txt) |
| BoTorch | Copyright (c) Meta Platforms, Inc. and affiliates. | MIT；`licenses/classic/botorch/`、`licenses/modern/botorch/` |
| GPyTorch | Copyright (c) 2017 Jake Gardner | MIT；`licenses/classic/gpytorch/`、`licenses/modern/gpytorch/` |
| scikit-learn | The scikit-learn developers；不同固定版本的原始年份与组件声明按各自 COPYING 保留 | BSD-3-Clause；`licenses/classic/scikit-learn/`、`licenses/modern/scikit-learn/` |
| Qt / PySide6 / Shiboken 6.12.0 | The Qt Company Ltd. 及源码／模块中列出的其他版权人 | 本应用采用 LGPLv3 许可路径并动态链接；`licenses/manual/qt-6.12.0/` 及运行时许可目录 |

其他依赖及其传递组件的声明保留在 `licenses/classic/`、`licenses/modern/`、`licenses/manual/`。清单可能同时包含仅供构建或测试的工具，不代表清单中每个组件都进入最终二进制。保留这些声明不会把它们的版权归属转移给 NaNoBO。

## 固定版本与修改

固定上游提交及实际兼容性修改见 [docs/UPSTREAM_MODIFICATIONS.md](docs/UPSTREAM_MODIFICATIONS.md) 和相应 `upstream/*/UPSTREAM_REVISION`。已修改的上游文件应继续保留原版权，并带有显著修改标记。不得将这些兼容性修改描述为重新发明上游算法。

- Gryffin：由原始 `.pyx` 重建 C 扩展，保留来源和修改标记。
- Atlas：采集优化器适配及已知约束的原单位解码修正。
- Olympus：源码快照版本与元数据加载兼容修正。
- BO-MCP：保留固定 `bo-engine` 兼容后端。新版 NaNoBO 增强工作流直接调用 BoTorch／scikit-learn，不将其归为 BO-MCP 全产品或原创算法。

## 二进制再分发

安装包应携带本文件、完整的适用许可证、NaNoBO 对应源码及构建说明。Qt/PySide6、DEAP、moocore 等适用组件的对应版本源码档案和校验清单按 [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md) 提供；不能仅放论文链接或库主页代替对应源码。用户依相应许可证享有的修改、替换、重新链接和调试权利不因 NaNoBO 的打包而被取消。

公开发行文件应使用同一版本的应用源码、依赖版本和源码档案。新平台或依赖升级后应重新生成清单。参考文献和致谢分别见 [REFERENCES.bib](REFERENCES.bib)、[ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md)；它们不能代替本节所需的法律材料。

本项目没有获得以上作者或机构对 NaNoBO 的官方背书；不得借用其名称暗示授权认证、合作或性能保证。
