# 第三方许可与对应源码

核查日期：2026-10-31。本文记录本次选用版本的许可证据、随附文件和发行者仍需核对的事项，不是法律认证。Gryffin 允许再分发，不等于包含 Qt、科学计算库的整个安装包自动完成全部许可义务。

## 可以上传什么

可以将本项目自己的界面和构建代码，以及按各自许可证保留声明的上游代码，上传到自己的 GitHub。Gryffin 为 Apache-2.0；Atlas、BO-MCP 等的许可正文保存在 `licenses/upstream/`。第三方代码仍受各自许可证约束，不因项目根目录采用 Apache-2.0 而改变。不要把该独立界面称为上游官方产品，也不要暗示原作者背书。更完整的上游核查见 `research/license_audit.md`。

分发安装包时，应将对应版本的应用源码、构建说明、第三方声明及 LGPL 库对应源码一起提供。当前发布目录的安排是：安装包旁的 `Source-and-Licenses` 目录包含应用 `source.zip`、`licenses` 和 `library-sources`。上传 GitHub Release 时应同样保留这些附件及下载路径；本地目录结构不是已经存在的公开下载地址。

## 本次保存的证据

| 内容 | 位置 | 证据与边界 |
| --- | --- | --- |
| 安装环境的精确依赖版本、元数据、已收集的 LICENSE/NOTICE | `licenses/classic/`、`licenses/modern/` 中的 `dependency-inventory.json` 及同级文件 | 由实际环境收集；安装环境也含构建工具，不等同于最终二进制模块清单。Windows 构建需要重新生成自己的清单。 |
| 固定优化器源码的许可证 | `licenses/upstream/` | 与各上游固定 SHA、修改记录一起保留。BO-MCP 的 `bo-engine` 由其仓库 MIT 许可证覆盖。 |
| PySide6 / Shiboken、Qt 6.12.0 许可正文 | `licenses/manual/qt-6.12.0/pyside/LICENSES/` 及各 Qt 模块的 `LICENSES/` | 经官方 SHA-256 校验的 6.12.0 源码档案中的 LGPLv3、GPLv3 等原文；同时保留源码内的历史 COPYING，不据此改变当前模块的许可选择。 |
| Qt 6.12.0 内含第三方组件归属 | `licenses/manual/qt-6.12.0/qtbase/`、`qtsvg/`、`qtimageformats/`、`pyside/` | 保存 85 份 `qt_attribution.json`、相应许可原文及引用的 Python PSF 归属文件。包含未必进入本应用的平台或可选组件；最终按实际携带模块确认适用范围。 |
| torchbnn 1.2 的 MIT 正文 | `licenses/manual/torchbnn-1.2-MIT-LICENSE.txt` | 从作者仓库发布年代已存在的 LICENSE 取得，Copyright 2019 Harry Kim。轮子的元数据声明 MIT，但轮子未附正文。 |
| pyDOE 0.3.8 的 BSD-3-Clause 正文及作者归属 | `licenses/manual/pyDOE-0.3.8-BSD-3-Clause-LICENSE.txt`、`pyDOE-0.3.8-AUTHORS-NOTICE.txt` | 许可证取自 2014 年历史版本；保留 2015 年 0.3.8 原始发行包中的作者说明。未用 2025 年新版版权声明替代老版本。 |
| 手动取得文件的 URL 与散列 | `licenses/manual/SOURCES.json` | Qt 6.12.0 文件从经官方 SHA-256 验证的源码档案提取，记录档案成员路径和本地 SHA-256；其他文件记录精确历史 URL、发行包校验值。 |
| LGPL 库的完整官方源码压缩包 | 发布材料中的 `library-sources/` | 精确版本和 SHA-256 见该目录的 `SOURCE-ARCHIVES.json`、`SHA256SUMS.txt`。这些档案与应用 `source.zip` 分开提供。 |

Qt 在线文档会随版本更新；本次原文从官方 6.12.0 精确版本源码档案取得，不能将在线新版表直接当成本包的版本清单。旧版 6.8.3 的许可、散列和源码仅保留为本地开发历史，不随本源码或新版安装包混发。

## Qt / PySide6 的具体处理

本应用选择 PySide6-Essentials / Shiboken 6.12.0 的 LGPLv3 路径，使用动态库形式的 QtCore、QtGui、QtWidgets、QtSvg 等。Qt 另有 GPL-only 模块；Essentials 包名也不等于只含 QtBase：本应用实际图片插件使用 QtSvg 与 QtImageFormats，所以对应源码一并随附。当前构建不需要 QtCharts、QtDataVisualization、QtPdf 或 WebEngine，并排除 PDF 图片插件 `qpdf`；正式发布前仍应检查打包工具实际收集了什么。

发行者应落实以下事项：

1. **保留明显声明和许可正文。** 应用“关于 / 许可”说明使用 Qt/PySide6，并允许打开随附许可目录；安装包及其附件保留 LGPLv3、GPLv3 和相应第三方声明。
2. **提供实际使用库的对应源码。** 已准备 Qt 6.12.0 的 `qtbase`、`qtsvg`、`qtimageformats`，以及 PySide/Shiboken 6.12.0 的 `pyside-setup` 官方源码压缩包。它们包含自身构建文件和原始许可。最终如果额外带入其他 Qt 模块，需同时补充其精确源码、补丁和相应构建信息。只有本应用 Python 源码，或仅放一个 Qt 首页链接，不能替代库对应源码的交付。
3. **允许用户修改、替换、重新链接和调试。** 本项目不禁止为调试库修改而进行的逆向工程，不要求联网授权来运行用户重建的程序，也不以产品条款限制 LGPL 授予的权利。修改者可以使用随附应用源码及构建脚本，以自己重建的兼容 Qt/PySide6 重新打包。直接替换动态库时应保持 ABI、Python 和架构兼容；Mac 修改会使旧签名失效，可自行重建并作本地签名，而不是依赖原发布者的私钥。
4. **使源码可随二进制取得。** DMG 的 `Source-and-Licenses/library-sources` 与 Windows 安装器同页附件应包含下列压缩包，并保留校验清单。若改用书面源码提供承诺，需要另行落实有效期、接收地址和履行方式；本文没有代替发行者作出这种承诺。

6.12.0 的 LGPLv3/GPLv3 正文已与 6.8.3 保存副本逐字节核对一致。第三方组件和归属按本次精确版本重新收集，不能用旧组件清单代替。

本次对应源码的官方取得地址：

- [Qt 6.12.0 子模块官方目录](https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/)：`qtbase-everywhere-src-6.12.0.tar.xz`、`qtsvg-everywhere-src-6.12.0.tar.xz`、`qtimageformats-everywhere-src-6.12.0.tar.xz`；每个档案的 `.sha256` 端点提供官方散列。
- [PySide6 6.12.0 官方源码目录](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/)：`pyside-setup-everywhere-src-6.12.0.tar.xz`，同样核对官方 `.sha256`。
- 固定标签的官方镜像：[PySide / Shiboken](https://github.com/pyside/pyside-setup/tree/v6.12.0)、[Qt Base](https://github.com/qt/qtbase/tree/v6.12.0)、[Qt SVG](https://github.com/qt/qtsvg/tree/v6.12.0)、[Qt Image Formats](https://github.com/qt/qtimageformats/tree/v6.12.0)。

义务依据为随附 LGPL/GPL 正文及 [Qt 官方 LGPL 义务说明](https://www.qt.io/development/open-source-lgpl-obligations)。动态链接不免除提供库对应源码、保留许可或允许用户替换库的要求。

## 其他运行库与构建工具

Windows 安装器使用 Inno Setup。简体中文消息文件由 Zhenghan Yang (Kira) 维护，取自 [Inno Setup 官方翻译目录](https://jrsoftware.org/files/istrans/) 所链接的官方源码。固定文件、原始署名、Inno Setup 许可和来源散列保存在 `scripts/localizations/`。安装器保留 Inno Setup 自带的版权和网站声明；该工具不属于 NaNoBO 的科研算法。

DEAP 1.4.4 的源码 `LICENSE.txt` 为 LGPLv3；moocore 0.3.2 的官方发行元数据标明 `LGPL-2.1-or-later`，其 `COPYRIGHTS` 说明 C 库大部分文件采用 MPLv2，因包含 AVL 树组件，组合库按 LGPLv2.1 或更高版本分发。它们的精确 PyPI 源码发行包随 `library-sources/deap/`、`library-sources/moocore/` 提供，并对照 [DEAP 1.4.4 官方发行元数据](https://pypi.org/pypi/deap/1.4.4/json)、[moocore 0.3.2 官方发行元数据](https://pypi.org/pypi/moocore/0.3.2/json) 中的 SHA-256。moocore 的完整 LGPLv2.1、MPLv2 规范文本另存于 `licenses/manual/moocore-0.3.2-*.txt`；其各文件作者和其他所含组件的归属继续由未修改源码及 `COPYRIGHTS` 保留。

Windows 0.2.3 的经典环境为兼容 Gryffin 的 NumPy 1.23，固定使用 moocore **0.1.10**。该版本的 [官方发行元数据](https://pypi.org/pypi/moocore/0.1.10/json)、对应源码和 SHA-256 另记于 `docs/manifests/library-source-alternatives.json`。发布脚本按实际安装版本选择精确源码，并把实际清单写入 `library-sources/SOURCE-ARCHIVES.json`；不会用 Mac 环境的 0.3.2 源码代替 Windows 的 0.1.10。两种构建均保留实际版本源码中的原始版权和许可文件；版本依各自的依赖清单及构建记录区分。

torchbnn 的正确作者仓库是 [Harry24k/bayesian-neural-network-pytorch](https://github.com/Harry24k/bayesian-neural-network-pytorch)，其 [1.2 发行页](https://pypi.org/project/torchbnn/1.2/) 的安装说明也指向此处；安装包元数据中省略 `-pytorch` 的旧主页链接已无法访问。手动补充的 MIT 文件使用 [2019 年固定历史源码](https://github.com/Harry24k/bayesian-neural-network-pytorch/blob/361dc428bbe5bbe9470293730808d66b031e79f1/LICENSE)。pyDOE 的旧项目链接现重定向到新组织；本次使用 [2014 年固定 LICENSE](https://github.com/pydoe/pydoe/blob/7a78bfa72fc59cd7cc6f58b8a910dcfad7f605bd/LICENSE)，并保留原 0.3.8 作者说明。

Cython 3.3.0 仅在发布端从 Gryffin 原始 `.pyx` 重新生成 C 文件，许可为 Apache-2.0；构建脚本已显式排除 Cython 编译器。科学计算库中名称含 `cython` 的已编译扩展或随附 `.pyx` 不等同于分发 Cython 编译器，其许可由相应科学计算库保留。PyInstaller 的 bootloader 具有允许分发生成应用的许可例外；该例外不覆盖应用内其他库的独立义务。

## 公开二进制前的核对

当前已经取得许可正文、固定版本来源及对应源码档案；尚不能据此声称最终安装包通过法律认证。发布每个平台的最终产物时，需核对实际 DLL / framework / 扩展模块清单与本文件相符，确认没有意外加入 GPL-only Qt 模块，确认对应源码含该库使用的全部补丁和所需构建信息，并检查 `Source-and-Licenses` 真正进入 DMG 或与安装器在同一发布位置提供。Windows CI 的许可证应由 Windows 构建环境重收集，库源码和校验清单也必须放入同次发布材料；不得只上传 `.exe` 后省略这些附件。
