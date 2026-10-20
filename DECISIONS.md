= DECISIONS.md — 决策日志

追加式记录：被采纳的方案、被否决的替代方案、理由。旧方案归档于此，不留在主文档。

== 2026-10-09 仓库结构与接手基线

- 决策：以 `python-app/dxvk-version-manager-py` 现有仓库为唯一真相源（HEAD `e37991b`，远端 `github.com/Janlhin/DXVK_Manager` 私有）。
  `node-app`（Electron/MIT 克隆）与 `web-configurator`（GPL-3.0 克隆）维持「外部参考克隆」，不入库
  （与既有 `PLAN.md §30` 一致，避免 MIT+GPL-3.0 同库许可冲突）。
- 被否决的替代方案：把 `dxvk-manager` 整体建为 monorepo 纳入全部三应用——许可混用复杂度高，且
  node-app/web-configurator 本就是第三方克隆，无必要纳入版本控制。
- 理由：最小化许可风险，复用已推送的私有仓库与 GitHub 远端。
- 已知限制：工作区上层存在 `C:/Users/Janlhin/.git`（HOME 仓库，0 tracked 文件），会遮蔽本仓库；
  所有 git 操作须用 `git -C python-app/dxvk-version-manager-py` 显式指向，避免误改 HOME 仓库。

== 2026-10-09 接手期 UI backlog 全部保留为待裁决

- 决策：以下文档中标记为「待你定 / 仅记录」的 UI 项**不猜测实现**，全部转入 `TASKS.md` 待裁决队列：
  §22 封面圆角(B)、§24 列表右侧太空、§25 配置页卡片、§27 列头回归、§29 注释开关入配置页、
  §33 配置页信息模型重构、§26 两个写入规范、§28 英文版 i18n。
- 理由：歧义处理协议——多方案/不可逆/与既有约定冲突时禁止猜测推进。

== 2026-09-14 封面圆角方案选 B（缓存切片）

- 决策：封面圆角采用 B（缓存期切圆角/圆形变体），不采用 A（MultiEffect shader 遮罩）。
- 被否决的替代方案：A（shader 遮罩）——离屏 software 后端渲染不出、依赖 GPU、大库有开销。
- 实现（2026-10-09）：`covers.py` 新增 `ensure_card`（顶边两圆角 `*-card.png`）与 `ensure_round`
  （正圆 `*-round.png`），纯 Pillow、无 GPU；`models.py` 暴露 `coverCardUrl`/`coverRoundUrl`，
  保留 `coverUrl`（原图给详情弹窗）；`bridge.py` 取封面时生成两种变体并以 `coverReady(key,card,round)`
  下发；`GameCard.qml` 绑 `coverCardUrl`、`GamesPage.qml` 列表头像绑 `coverRoundUrl`。
- 状态：**已实现，待 Windows 真机渲染验证**（沙箱无 PySide6/Pillow，无法跑 GUI）。
- 仍待裁决（§22.5 #2）：详情弹窗大封面是否也圆角——本次保持原图不动，留待你定。

== 2026-10-09 推进循环第一批裁决

- D1 GitHub 推送：用户选择「刷新 token scope」——运行 `gh auth refresh -s workflow` 后重新推送。
- D2 T11 列表右侧太空：用户选择**方案 A**（名称列 + 元数据列，三列填满行宽）。
  被否决方案 B（整行限宽 1100，右侧仍有空白）。
- D3 T13 配置页信息模型重构：用户选择**现在就做**。
  按场景分组 + 作用域选择 + 已改清单（§33），约 733 行 ConfigPage.qml 重写。
- D4 T16 作者身份改写：用户选择**现在改写**。git filter-repo 批量改写，需先备份。
  不可逆操作，用户已知情并同意。

== 2026-10-14 推进循环第二批裁决

- D5 T12 列头排序：用户指令直接推进，按 §27 既定方案（资源管理器式列头）实现；
  列头点击复用 models.py 既有 `set_sort` 列头语义，DXVK 列与状态徽标对齐。
- D6 T14 注释开关：按 §29 既定组合——候选 A（预览栏就地开关）+ 方案 ①
  （与设置页共用 `conf_comments` 同一键），未采用独立设置键。
- D7 T15 英文版 i18n：用户选择**全量落地（路线 A：qsTr/lupdate/lrelease）**，
  否决字典/运行时替换路线。预设名（性能优先/兼容优先/纯净）为逻辑键保持中文不译；
  选项说明语言独立于界面语言（confkit `_en` 字段）；语言切换重启生效。
- D8 T17 node-app / web-configurator：明确排除出仓库（详见 TASKS.md T17 行），
  许可隔离依 §30，正本在 C 盘源目录。
- D9 伞形库远端：用户选择 `Janlhin/DXVK_Manager-workspace` · **私有**；
  py 工程远端维持 `Janlhin/DXVK_Manager`（私有）不变，两库各自独立推送。

== 2026-09-13 架构决策：暂不换前端

- 决策：核心层（3030 行）与 UI 解耦，保持 PySide6/Qt 前端，换架构（WebView2/Qt 重写）暂缓。

== 2026-10-15 配置页提示排版与文档角标（§34 / T21）

- 现状：`OptionGroup.tooltip()` 全文经 DarkTip 以单段纯文本显示——中文说明、示例、
  DXVK 英文原文糊成一段，无分区、不滚动、高度不封顶，Reflex 类长原文直接溢出屏幕。
- 决策：选项行 label 右侧加 ⓘ 角标，点击打开可滚动文档卡——说明 / 示例 / DXVK 原文
  三区排版，示例与原文用等宽暗底代码块，整体高度封顶窗口 70%，✕ 与点击外部关闭；
  数据走 `ConfigListModel` 选项行新增 `doc` role（Python 侧 `tooltip()` 一次生成，
  零额外查询）；悬停 DarkTip 保留为快速摘要入口。
- 被否决替代：仅加滚动条不改分区（排版层次依旧差）；改用 Markdown 渲染
  （TextEdit Markdown 对代码块样式控制弱，且上游原文不是规范 Markdown）。
- 理由：核心层已可 100% 复用，等功能待办清完、界面不再大改后再评估重构（见 `TASKS.md` 的 bridge 拆分）。

== 2026-10-15 项目许可变更为 GPL-3.0

- 决策：本项目代码许可由 MIT 变更为 **GPL-3.0**（GNU General Public License v3.0）：
  `LICENSE` 全文替换为 GNU 官方 GPLv3 文本；`README.md`「许可证与致谢」与
  `THIRD_PARTY_NOTICES.md`（首句、§4 结语）同步更新；版权行 © 2026 DXVK Version Manager
  （Python edition）贡献者随 README 保留。
- 被否决的替代方案：沿用 MIT——与「项目 License 是 GPL 3.0」的明确定位不符。
- 理由与影响：① 版权人自主的单向兼容变更，无第三方障碍（PySide6/Pillow 为运行时依赖、
  不并入源码；`assets/dxvk.conf` 为 zlib，可并入 GPL 项目）；② 与 §30「外部参考克隆
  不入库、不复制代码」的隔离决策不冲突；③ GitHub licensee 识别将由 MIT 自动更新为
  GPL-3.0；④ v1.0.0 Release 说明补充「许可证」章节。

== 2026-10-20 代码与架构审计

- 决策：**写盘与回滚一律原子化**。备份、还原、写 `dxvk.conf`、缓存版本目录安装
  统一走「同目录临时文件 → `os.replace`」；安装时架构自检失败必须**把原件从 `.bkp`
  移回**，而不是只删掉新拷贝。被否决方案：先 `unlink` 再 `rename`（进程中断时原件与
  备份可能同时消失）。
- 决策：**「正在使用」的版本按归一化版本号比较**。GPLAsync 缓存目录不带前导 `v`，
  账本存 `v2.7-1`；统一用 `_version_name()`（去 `v`、小写）比较，`clear_cache(keep_used=True)`
  才真正保护运行中的版本。被否决方案：改账本存储格式（涉及既有用户数据迁移）。
- 决策：**下载先解压到 `<版本>.part` 暂存目录，校验 x32/x64 布局后再换入**；
  失败或取消时删除暂存目录，不再留下「看着已安装、实际为空」的版本目录。
- 决策：**门禁必须是真门禁**。`verify.ps1` 逐步检查 `$LASTEXITCODE`（PowerShell 5.1
  不会因原生命令非零而中止，旧脚本在 ruff/pyright 失败时仍退出 0），并按
  `.venv → py -3 → python` 探测解释器（本机 `py -3` 未注册任何发行版，旧脚本根本跑不起来）；
  `verify` 改为跑 `pytest tests` 全量并显式执行 `test_conf_golden.py`（该文件此前被
  pytest 收集为 0 个用例，实际从未进入门禁）。CI 无 PySide6 时模型测试自动跳过。
- 决策：**文档据实修正，不保留「曾经的实现」叙述**。README 的页面结构 / 数据目录 /
  检测顺序、`MANIFEST.md` 的资源哈希、`TASKS.md` 的 T13/T35 状态按当前代码改写；
  `TAKEOVER.md` 作为 2026-10-09 的接手快照保持原样，不再当作现状说明。
- 决策：**死代码与拆分不在本次擅动**。审计列出的无引用符号转入 `TASKS.md` T36，
  `bridge` / `steam` / `ConfigPage.qml` 的拆分转入 T37，两者均按 `AGENTS.md`
  的删除分级与「待裁决」流程等待拍板，避免一次提交混入重构与行为变更。
- 理由：本轮问题集中在「失败路径」——正常路径有测试覆盖，异常路径（备份失败、架构不符、
  下载中断、外部改动）没有，于是静默丢状态。原子化 + 回归用例是成本最低的止损方式。

== 2026-10-20 死代码清理与检测层拆分（T36 / T37）

- 决策：**T36 按「无引用即清」执行**，删除休眠模块 `metadata.py`、`covers.py` 的 Tk 遗产、
  `util`/`steam`/`sources`/`confkit` 中七个无调用方符号，以及 `bridge.coverUrlFor` 空实现。
  被否决方案：保留 `metadata.py` 作为「未来封面源」——一个既不在调用链、又被文档描述为
  能力的模块，只会误导读者；T35 真正落地时按当时的数据源（IGDB / SteamGridDB）重新实现，
  不保留投机代码。
- 决策：**检测层拆到 `detect.py`，但不按 launcher 拆 `steam.py` 包**。launcher 发现函数被
  测试用 `mock.patch.object(steam, ...)` 直接替换，拆包会让补丁打在错误的模块上，收益低、
  回归风险高；检测层与发现层无共享状态，拆分零风险，并让 `installer` 不再反向依赖发现层。
- 决策：**配置目标存储与预设抽到 `ui/config_store.py`（无 Qt），不做多 QObject 大拆**。
  多 QObject 方案要改 QML 的 context property 与全部 `bridge.*` 调用点，而当前没有 QML
  交互测试，无法验证回归；先把可单测的部分抽出来，桥接拆分留作 T37 剩余项。
- 理由：以「可验证」为边界——有测试护栏的部分动手，无验证手段的部分如实记录，不假装完成。

== 2026-10-20 QML 组件化与桥接拆分（T37 收尾）

- 决策：**先织网，再重构**。T37 此前被推迟的理由是「缺少 QML 交互测试手段」。本次先补
  `tests/qml_check.py`（纯标准库：相对 import 可解析、同文件 id 唯一、`qsTr` 词条与
  `objectName` 对基线）与 `tests/qml_components.py`（离屏逐个加载组件），再动结构。
  被否决方案：直接上 `qmllint` 当门禁——`bridge`/`configModel` 是运行时注入的 context
  property，qmllint 无法静态解析，实测产出 195 条 `unqualified` + 49 条
  `missing-property` 假阳性，噪音淹没真问题。
- 决策：**QML 组件同目录拍平，靠隐式导入互引，不写 `import "path/X.qml"`**。
  本环境无法可靠解析相对路径导入，写了会让页面直接加载失败（`Type ConfigPage
  unavailable`）——这是提交 `8aa3159` 引入的真实回归，靠新增的错误特征
  （`no such directory` / `unavailable`）才被门禁抓到，因未推送故未污染远端历史。
- 决策：**CI 不装 PySide6**。组件级测试需要 200MB 下载与 Linux 系统库依赖，会让流水线
  变脆；`qml_check.py` 进 CI，`qml_components.py` 只进本地 `verify.ps1`。
- 决策：**QML 拆分保持 `objectName` 与全部 `qsTr` 源串不变**。两者进入基线文件，
  拆分只是搬运，不翻译任何界面文字。
- 决策：**桥接用 facade + 领域服务，QML 侧零改动**。`ui/bridge.py`（1306 行）拆为
  `ui/bridge/` 包：`facade.py` 保留全部 `@Slot`/`Signal` 签名，`library`/`versions`/
  `config`/`settings` 四个服务各自负责一个领域，`jobs.py` 承载线程池、忙碌引用计数与
  在途任务去重。被否决方案：让 QML 直接调用四个子对象——那要改 context property 与
  全部 `bridge.*` 调用点，收益远小于风险。
- 决策：**翻译上下文显式固定为 `Bridge`**。`QObject.tr()` 以类名为 context；服务是普通
  Python 类，若直接沿用会改用服务类名，英文词库静默失效而不报错。`base.py` 因此
  用 `QCoreApplication.translate("Bridge", ...)` 而非 `self.tr()`。
- 决策：**加一道桥接契约测试**。`tests/test_bridge_contract.py` 钉住 56 个槽与 15 个
  信号的名称与参数个数——这是「QML 零改动」这个承诺唯一能被自动验证的形式。
- 理由：这一轮的核心不是把代码变小，而是**让重构变得可验证**。截图逐像素对比、词条
  基线、槽签名基线、组件级离屏加载，四张网都在，证明拆分确实只是搬运。

== 2026-10-20 配置生成器独立成软件（`dxvk_toolkit/standalone`）

- 决策：**独立配置器复用现有代码，不复制组件**。新建 `dxvk_toolkit/standalone/`：
  入口（`app.py`）、桥接（`bridge.py`，22 个槽）、独立设置（`store.py`）、
  独立资产定位（`assets.py`）与两个 QML 文件（`StandaloneMain.qml`、
  `ConfiguratorPage.qml`）。配置核心 `confkit`、选项模型 `ui/conf_model.py`
  与配置页的 QML 组件（`ConfigToolbar` / `ConfigContextBar` / `ConfigRail` /
  `ConfigOptionList` / `ConfigPreviewPane` / `ConfigPresetDialog`）全部**原样复用**，
  只给它们加了参数（`showTarget` / `showImport` / `emptyText` / `descriptionText` /
  `builtInNoteText` / `mode` / `writeEnabled`）来适配两种语义。
- 决策：**共享组件靠「QML 文件名决定翻译 context」这一条实现一份词库服务两个程序**。
  Qt 的 `qsTr()` 翻译上下文是调用所在的 `.qml` 文件名，与哪个应用加载它无关，
  因此一份 `app_en.qm` 同时覆盖主应用与独立配置器。`tests/i18n_fill.py` 改为
  扫描两棵 QML 树，`tests/qml_check.py` 相应拆成 app / standalone 两份基线。
- 决策：**独立配置器不 import `dxvk_toolkit.paths`**。该模块在 import 时就会
  创建主应用的数据目录并读取其 `settings.json`，独立工具绝不能碰。因此
  `ui/config_store.py` 的 `settings` 参数改为**懒加载**（默认才走主应用），
  独立工具传入自己的 store；资产定位另起 `standalone/assets.py`。
- 决策：**语义差异只保留一处** —— 主应用的「目标」是游戏目录，独立配置器的
  「目标」是 `.conf` 文件本身（打开 → 改 → 保存回去）。因此
  `build_conf()` 增加了 `header` 参数，独立工具写自己的文件头
  `Generated by DXVK Configurator`，不冒用主应用的名字。
- 决策：**桥接是新的，不是主应用桥接的裁剪版**。主应用 56 个槽里大部分是
  扫游戏、下版本、装 DLL，与「给定 dxvk.conf 生成定制版」无关；照搬会让
  独立工具背上 Steam 扫描与版本缓存的依赖。
- 决策：**退出顺序显式收尾**。窗口销毁必须早于桥接回收，否则 QML 绑定在
  最后一轮求值时拿到 null，报一片 `Cannot call method ... of null`。
  `standalone/app.py` 的 `_shutdown()` 先 `deleteLater()` 根对象再
  `processEvents()`，桥接本身 parent 到 `QApplication` 以延长寿命。
- 理由：用户只需要生成器时不该被迫安装整个版本管理器，但复制一份组件
  意味着两套界面从此各自漂移。复用 + 参数化让「独立发布」这件事不产生
  第二份真相。
