# Qt 6.12.0 对应源码核查

2026-10-31：本次正式采用 PySide6-Essentials / Shiboken 6.12.0。精确版本官方源码和散列记录在 `library-sources.json`，原文摘录位于 `licenses/manual/qt-6.12.0/`。

PyPI 官方元数据仍列出 `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`；本项目仍选择 LGPLv3 路径。Qt Base 与 PySide/Shiboken 的 `LICENSES/LGPL-3.0-only.txt`、`GPL-3.0-only.txt` 已与旧版 6.8.3 保存副本逐字节比较，正文相同。这不表示各版本的所有第三方组成相同，6.12.0 归属应从新的源码中收集。

官方出处：

- [PySide6-Essentials 6.12.0 发行和许可证](https://pypi.org/project/PySide6-Essentials/6.12.0/)
- [Qt 6.12.0 官方子模块源码](https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/)
- [PySide/Shiboken 6.12.0 官方源码](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/)

原生界面与冻结应用验证已通过，已切换发行清单。旧版6.8.3许可/源码仅保留为本地开发历史，不混入本源码或新版发行附件。QtSvg 与 QtImageFormats 由实际图片插件决定，不能从 Essentials 包名推断不含它们。PDF图片插件若依赖未携带的QtPdf，应从本应用收集中排除。
