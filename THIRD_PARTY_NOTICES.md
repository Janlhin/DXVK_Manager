# 第三方组件与致谢

本程序（GPL-3.0）在实现与数据上依赖或参考了以下项目。

## 1. DXVK — 内置配置参考文件

* 项目：https://github.com/doitsujin/dxvk
* 许可证：zlib
* 使用方式：`assets/dxvk.conf` 是该仓库 `dxvk.conf` 的原文副本。
  配置生成器的全部选项、说明、类型判断与默认值都从这个文件解析而来，
  程序不会修改它。运行时下载的 DXVK 版本由用户自行安装，授权随各自发布包。

zlib 许可证要求：本软件按「原样」提供，不附带任何明示或暗示的担保；
若分发时使用了源代码，不得声称本软件为原始作者的作品；若二进制分发中使用了
该软件，需在文档中注明来源。本文件即该注明。

## 2. DXVK-gplasync — 可下载的版本来源

* 项目：https://gitlab.com/Ph42oN/dxvk-gplasync
* 使用方式：仅通过网络列出版本并下载官方发布的压缩包，不包含其代码。
  相关权利与许可以该项目自身为准。

## 3. artmakh/dxvk-version-mananger — 功能蓝本（MIT）

* 项目：https://github.com/artmakh/dxvk-version-mananger
* 许可证：MIT
* 使用方式：本项目为独立实现，**没有复制其源代码**：
  JavaScript 源码仅被阅读以确定行为（Steam 库解析、版本来源、
  `<dll>.bkp` 备份/还原策略、按 Direct3D 版本选择 DLL 的规则），
  再用 Python 独立实现，并在此基础上修正了若干限制（见 README 的「与原版的差异」）。

## 4. CamoMano/DXVK-Configurator — 功能蓝本（GPL-3.0）

* 项目：https://github.com/CamoMano/DXVK-Configurator
* 许可证：GPL-3.0
* 使用方式：本项目实现了它所演示的能力（从 dxvk.conf 解析选项、
  生成 dxvk.conf），但**没有复制其任何代码**：被解析的数据文件 `dxvk.conf`
  本身来自上游 DXVK（zlib，见第 1 节），而不是这个 GPL 仓库的独创内容；
  解析与生成的行为属于不受版权保护的功能与算法，且本实现以另一种语言、
  另一种结构重新编写（解析器、类型系统、分组与导出均在
  `dxvk_toolkit/confspec.py` 与 `confbuild.py` 中独立完成）。
* 备注：本程序自身自 2026-10-15 起以 GPL-3.0 分发（见 `LICENSE`）。

## 5. 运行期访问的第三方服务

| 服务 | 用途 | 说明 |
| --- | --- | --- |
| api.github.com / github.com | 列出并下载 doitsujin/dxvk 发布版本 | 未认证请求有速率限制，程序内置 atom feed 与本地缓存兜底 |
| gitlab.com | 列出并下载 Ph42oN/dxvk-gplasync 发布版本 | 失败时使用本地缓存 |
| pcgamingwiki.com | 查询无法本地识别的游戏的 Direct3D 信息 | 可选，结果缓存 45 天 |

以上请求只发送必要的版本号 / AppID，不发送任何用户标识。
