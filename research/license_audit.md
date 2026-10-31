# Gryffin 桌面应用与 GitHub 再发布许可核查

> 历史调研记录。当前公开分发以根目录 THIRD_PARTY_NOTICES.md、ACKNOWLEDGMENTS.md 和 docs/THIRD_PARTY.md 为准。

核查日期：2026-10-31。Gryffin 已对本地下载源码 commit `fb149d18f9c81b96179cc682c46e05db60bc7229` 核对；其他对象为官方公开分支。安装包最终依赖尚未锁定，本报告不等同于最终二进制的完整许可证清单。

## 结论

**可以把 Gryffin 源码、修改版本和集成它的桌面应用发布到自己的 GitHub，并可分发安装包；前提是履行相应开源许可义务。** Gryffin 官方 `LICENSE.md` 为 Apache License 2.0，授权范围包括复制、修改及源码/二进制分发。无需仅因进行再发布而另行取得项目作者同意。[Gryffin LICENSE](https://github.com/the-matter-lab/gryffin/blob/master/LICENSE.md)

旧 `aspuru-guzik-group` 仓库链接目前重定向 `the-matter-lab`。发布时应记录实际使用的 commit/版本，避免把今后的上游变化混入本次核查。

## 组件核查

| 组件 | 查到的许可 | 证据与核查程度 |
|---|---|---|
| Gryffin | Apache-2.0 | 已读 [固定 commit 的 LICENSE.md](https://github.com/the-matter-lab/gryffin/blob/fb149d18f9c81b96179cc682c46e05db60bc7229/LICENSE.md) 及本地副本；文件末尾版权为 Copyright (C) 2020, Harvard University |
| Atlas | MIT | 已读 [LICENSE 正文](https://github.com/the-matter-lab/atlas/blob/main/LICENSE)，保留 Copyright (c) 2022 rileyhickman |
| Olympus | MIT | 已读 [LICENSE 正文](https://github.com/the-matter-lab/olympus/blob/main/LICENSE)，保留 Copyright (c) 2020 Aspuru-Guzik group repo |
| Chimera | 仓库标识为 MIT | [官方仓库](https://github.com/the-matter-lab/chimera)；此次正文抓取失败，正式随包前以下载源码中的 LICENSE 为准 |
| Phoenics | 仓库标识为 Apache-2.0 | [官方仓库](https://github.com/the-matter-lab/phoenics)；此次正文抓取失败，正式随包前以下载源码中的 LICENSE 为准 |

MIT 组件可复制、修改、发布和销售，但其版权与许可声明必须随副本/实质部分保留。各组件保留自己的许可，不能仅用应用根目录的新许可证覆盖上游声明。[Atlas MIT 正文](https://github.com/the-matter-lab/atlas/blob/main/LICENSE)、[Olympus MIT 正文](https://github.com/the-matter-lab/olympus/blob/main/LICENSE)

## Gryffin 具体发布处理

按照 Apache-2.0 第 4、6 条，应当：

1. 在源码仓库与安装包中附上上游许可证；保留适用的原始版权、专利、商标和归属声明。
2. 修改上游文件时，在被修改文件中显著说明修改；另记版本与修改摘要有利于追溯。
3. 如果实际使用的上游版本附带 `NOTICE`，分发时保留适用内容，并放在可读的文件、文档或通常显示第三方声明的界面中。本地固定 commit 的文件路径检索未发现独立 `NOTICE` 文件；仍须保留源码内适用声明。
4. 可以注明“使用 Gryffin / Atlas”，但许可不授予一般商标使用权；应用名称、图标和介绍不应暗示获得原作者或课题组官方背书。

Apache-2.0 不要求所有新增独立代码必须开源；本项目选择何种根许可证与对 GitHub 的可发布性是两个问题。沿用 Apache-2.0 是容易理解的方案，但应由项目所有者最终确定。以上为条款归纳，正式许可文本以英文原文为准。[Apache 官方许可，第 4、6 条](https://www.apache.org/licenses/LICENSE-2.0)

## 安装包仍需补齐的核查

Gryffin 的当前 `setup.py` 列出 NumPy、SQLAlchemy、Rich、pandas、matter-chimera、DEAP、PyTorch、torchbnn；这是直接依赖，并非全部传递依赖。实际安装包还会含 Python、GUI/打包运行时和原生库。需根据**最终构建环境**生成准确版本清单、收集各自 LICENSE/NOTICE，并检查 GUI 工具包等的额外分发义务。不能从“Gryffin 是 Apache-2.0”推导出整个安装包已经完成合规。[Gryffin setup.py](https://github.com/the-matter-lab/gryffin/blob/master/setup.py)

建议在仓库保留 `THIRD_PARTY_NOTICES.md` 和 `licenses/`；在应用“关于/开源许可”中提供读取入口。源码仓库不要上传虚拟环境、构建缓存、个人实验数据或凭据；发行二进制放 GitHub Releases。这里没有代用户创建或公开 GitHub 仓库。
