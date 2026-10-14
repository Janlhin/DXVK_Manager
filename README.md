# DXVK Version Manager · Python edition

一个**核心层纯标准库**的 Windows 桌面工具（图形界面需 PySide6、封面需 Pillow，均已在 `MANIFEST.md` 登记；核心层与命令行零第三方依赖）：

* 检测 Steam 游戏（含所有库文件夹）与手动添加的游戏目录
* 下载 / 管理官方 DXVK 与 DXVK-GPLAsync 版本
* 一键为某个游戏安装 DXVK（自动备份原始 DLL，可随时还原）
* **DXVK 配置生成器**：按官方 dxvk.conf 参考文件勾选选项，生成 dxvk.conf 并直接写入游戏目录

本项目是 [artmakh/dxvk-version-mananger](https://github.com/artmakh/dxvk-version-mananger)（Electron，MIT）
的 Python 重写版，并把 [CamoMano/DXVK-Configurator](https://github.com/CamoMano/DXVK-Configurator)
（GPL-3.0）所演示的配置生成能力合并了进来。代码为独立实现，详见「许可证与致谢」。

---

## 快速开始

需要 Python 3.10+（本机 `py -3.13` 已验证）。核心层与命令行**零第三方依赖**；图形界面需 `pip install PySide6 Pillow`（见 `MANIFEST.md`）。

    :: 启动图形界面
    py -3.13 main.py

    :: 或者双击（无控制台窗口）
    "DXVK Version Manager.pyw"

首次启动会自动扫描 Steam 库，并在后台识别每款游戏的 Direct3D 版本与架构；
识别结果会缓存到数据目录，之后启动是瞬时的。

## 界面

| 页面 | 作用 |
| --- | --- |
| **DXVK 版本** | 列出官方 DXVK 全部发布版本，下载 / 删除本地副本，显示大小与日期 |
| **GPLAsync 版本** | 同上，来源为 GitLab 上的 Ph42oN/dxvk-gplasync（async 分支） |
| **已安装游戏** | Steam + 多平台（Epic / GOG / Ubisoft / WeGame / 米哈游）+ 手动目录；Direct3D / 架构 / DXVK 状态 / dxvk.conf 状态；安装、还原、移除、打开目录 |
| **DXVK 配置** | 配置生成器：简单 / 进阶 / 完全 模式、搜索、实时预览、复制、导出、写入游戏目录 |
| **设置** | 代理、参考文件（内置 / 自定义 / 按 tag 在线获取）、数据目录、缓存清理 |

## 命令行

不用图形界面也能完成全部事情：

    py -3.13 main.py --scan-games                     # 列出检测到的游戏
    py -3.13 main.py --versions --limit 10            # 列出可下载版本
    py -3.13 main.py --download v2.7.1                # 下载并解压一个版本
    py -3.13 main.py --install v2.7.1 --game "D:\Games\Foo"
    py -3.13 main.py --restore  --game "D:\Games\Foo"
    py -3.13 main.py --status   --game "D:\Games\Foo"
    py -3.13 main.py --fingerprint --game "D:\Games\Foo"     # 识别已有的 DXVK：版本 + 哈希比对
    py -3.13 main.py --adopt --game "D:\Games\Foo"           # 接管已有安装（--backup-system 补还原点）
    py -3.13 main.py --gen-conf --set hud=fps --set maxFrameRate=60 -o dxvk.conf

## 它把文件写到哪里

全部集中在 `%LOCALAPPDATA%\DXVK-Version-Manager-Py`：

    settings.json            设置
    games.json               已安装 DXVK 的记录（哪款游戏、哪个版本、何时）
    dxvk-cache\<版本>\       解压好的官方 DXVK（x32 / x64）
    dxvk-gplasync-cache\     解压好的 GPLAsync 版本
    releases\                版本列表缓存（离线时也能显示）
    cache\detection.json     游戏的 Direct3D / 架构识别缓存
    games-meta\              PCGamingWiki 元数据与封面缓存
    logs\app.log             运行日志

游戏目录里只会出现两类文件：DXVK 的 DLL，以及安装时生成的 `<原名>.bkp` 备份。
点「还原原始 DLL」会把备份改回原名并删除 DXVK 的 DLL。

## 实现要点

* **Steam 检测**：读注册表得到 Steam 安装位置，再解析 `libraryfolders.vdf`
  与每个 `appmanifest_*.acf`，因此 D 盘等其他库文件夹的游戏也能被发现。
* **Direct3D 识别（离线）**：按信号强度依次使用 —— 游戏根目录自带的 D3D 运行库 DLL、
  D3D12 Agility SDK 标记文件（`D3D12Core.dll` 等，被加壳的游戏也带）、
  主 exe 的 PE 导入表、其余 exe 的导入表，最后才是 exe 中出现的模块名字符串
  （引擎常在次要代码路径里提到别的 D3D 模块，所以放在最后以防误判）。
* **架构识别**：直接读 PE 头（`IMAGE_FILE_MACHINE`），不依赖外部库。
* **DXVK 指纹识别与接管**：游戏目录里「不是本工具装的」DXVK 也能认出来 ——
  VERSIONINFO 资源读 `ProductName="DXVK"`（判定是 DXVK），
  真实版本号从二进制内嵌的 banner 字符串（`…DXVK: \0v3.1.1\0…`）提取
  （DXVK 故意把 FileVersion 伪装成 Windows 系统版本，资源里读不到），
  再对本地下载缓存里的全部官方 DLL 做 SHA-256 比对：
  命中 = 「官方原版 vX.Y 未经修改」，不命中 = 「与本地缓存不符（魔改/非官方构建，或该版本未下载过）」。
  确认后可一键「接管」：写入安装记录、（可选）从 System32/SysWOW64 补建还原点、
  之后即可正常升级。未接管的目录会被安装流程拦截，避免把 DXVK 的 DLL 备份成"原始文件"。
* **网络**：标准库 `urllib`，失败时自动重试，并回退到系统 `curl.exe`；
  代理默认「先直连，失败后尝试 Windows 系统代理」。
* **版本列表**：优先 GitHub API；触发限流（未认证 60 次/小时）时自动改用
  release atom feed + 可预测的下载直链；再不行就用本地缓存。
* **配置生成器**：`dxvk.conf` 是唯一数据源 —— 解析其中的注释块、示例值与类型，
  按文件里的顺序呈现选项，因此 DXVK 新增选项时不需要改代码。
  生成时一个选项会写入它出现的**所有** section（例如 `dxvk/dxgi/d3d9.maxFrameRate`），
  并且沿用参考文件自身的写法：`Auto`、`12_1`、`10DE` 这类枚举值不加引号，
  含空格或引号的值才加引号（DXVK 解析时会剥离引号，两种写法都合法）。

## 与原版的差异

保留：Steam 游戏检测、官方 DXVK 与 GPLAsync 版本下载、按 Direct3D 版本决定 DLL 组合、
`.bkp` 备份与还原、dxvk.conf 生成。

改进：

* 所有 Steam 库文件夹都会扫描（原版硬编码 `C:\Program Files (x86)\Steam\steamapps`）
* 游戏识别完全离线（原版依赖 PCGamingWiki 接口；这里作为兜底，结果缓存 45 天）
* GitHub 限流不影响使用（原版只调 API 且未分页，最多只能看到 30 个版本）
* 配置生成器：简单模式覆盖 9 个常用项（原版 3 个）、支持搜索、
  切换 简单/进阶/完全 模式不会清空已填内容、生成文件带注释小节
* 中文界面、命令行接口、纯标准库（原版需要 Node/Electron 运行时）
* 外来 DXVK 安装可指纹识别并接管（原版没有安装记录概念，混装后无法升级/还原）

未实现：封面图显示（元数据里有 URL，但界面暂不渲染图片）。

## 开发 / 校验

本项目遵循《用 AI 做项目：强制工程校验方案》。本地与 CI 共用唯一验收入口 `verify`：

    # Windows
    py -3 -m pip install -r requirements-dev.txt
    .\verify.ps1

    # Linux / CI
    python -m pip install -r requirements-dev.txt
    bash verify.sh

推送（或开 PR）后由 GitHub Actions（`.github/workflows/verify.yml`）权威判定：跑 `pytest` 核心套件、
`ruff` 静态检查、以及 PR 提交信息的 Conventional Commits 规范。GUI 冒烟测试 `tests/qml_smoke.py`
需要显示环境，不在无显示 CI 的必过门禁内。第三方来源登记见 `MANIFEST.md`；AI 协作约束见 `AGENTS.md`；
决策与待裁决项见 `DECISIONS.md` / `TAKEOVER.md` / `TASKS.md`。

## 许可证与致谢

* 本项目代码：MIT（见 `LICENSE`）
* 内置的 `assets/dxvk.conf` 来自 [doitsujin/dxvk](https://github.com/doitsujin/dxvk)（zlib 许可），
  为该项目的配置参考文件原文
* DXVK © doitsujin 及贡献者；DXVK-gplasync 由 Ph42oN 维护；两者均由本工具下载安装，授权不变
* 功能灵感来自 artmakh/dxvk-version-mananger（MIT）与 CamoMano/DXVK-Configurator（GPL-3.0）：
  本项目未复制它们的源代码，仅重实现了其行为。详见 `THIRD_PARTY_NOTICES.md`
