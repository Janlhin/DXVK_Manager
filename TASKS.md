# TASKS.md — 任务队列（由差距清单转化）

字段：ID · 标题 · 类型 · 依赖 · 规模 · 状态 · 验收/下一步。
「待裁决」项须用户拍板后方可开工（见 `TAKEOVER.md` D3）。

| ID | 标题 | 类型 | 依赖 | 规模 | 状态 | 验收 / 下一步 |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | `verify` 聚合脚本（pytest stdlib 套件） | chore | — | 低 | ✅ 已建（本次基线） | `.\verify.ps1` 退出 0 |
| T2 | 四个文档（README/AGENTS/DECISIONS/MANIFEST）+ 接手报告 | docs | — | 中 | ✅ 已建（本次基线） | 结构校验通过 |
| T3 | CI 跑测试 + lint + commitlint | ci | T1 | 高 | ✅ 已建（本次基线） | push 后 GitHub Actions 全绿；⚠️ 2026-10-14 发现：pyright `--warnings` 语义为「有 warning 即 exit 1」，Linux runner 无 PySide6 必产生 import warning → 自 T9 接入起 CI **从未实际绿过**（T8/T18 的「CI 跑绿」当时为误记）；移除旗标（`152c705`）后 **CI 首次全绿**（run 38586625832） |
| T4 | commitlint 提交门禁配置 | chore | — | 低 | ✅ 已建（本次基线） | PR 提交信息符合约定式 |
| T5 | 声明 PySide6/Pillow 运行时依赖清单 | chore | — | 低 | ✅ 已完成 | MANIFEST.md 已登记 PySide6 6.12.0 / Pillow 12.3.0 + dxvk.conf SHA256；复现脚本实测输出已附 |
| T6 | 静态检查达标（ruff 零警告） | chore | T3 | 中 | ✅ 已完成 | `ruff check .` 退出 0；67 项违规已清零（38 F401+9 UP035+9 UP037+5 I001+2 E741+2 W292+1 UP031+1 F841）；`verify.ps1`/`verify.sh` 已接入 ruff 门禁；confspec re-export 加 `__all__` |
| T7 | 死代码治理（等价 knip：vulture/ruff unused） | chore | T6 | 中 | ✅ 已完成 | vulture 零报告（80% 置信度）；清理 4 项白名单死代码：parse.py 不可达代码、util.py 未使用参数 max_bytes、GameCard.qml 死属性 selected；`nul` 文件已由用户在 PowerShell 中手动删除（Windows 保留名） |
| T8 | 运行时边界 schema 校验（confkit 解析入口） | feat | — | 中 | ✅ 已建（本次） | `validate.py` + `parse`/`confspec` 守卫 + `tests/test_validate.py`；push 后 CI 跑绿 |
| T9 | 引入 pyright 类型检查（Python 无编译期类型） | chore | — | 中 | ✅ 已完成 | pyright 1.1.414 接入 verify.ps1/verify.sh + CI typecheck job；basic 模式；核心层零错误零警告；reportAttributeAccessIssue 降为 warning（PySide6/QML 动态属性假阳性）；util.py 类型注释修复（4 元组声明错误） |
| T10 | UI：封面圆角方案 B（缓存切片） | feat | — | 中 | ✅ 已建（本次，待真机验证） | `covers.ensure_card/ensure_round` 切圆角变体；`models` 暴露 `coverCardUrl`/`coverRoundUrl`；`bridge` 取封面时生成；QML 卡片绑 card、列表头像绑 round；详情弹窗保持原图（§22.5 待定） |
| T11 | UI：列表右侧太空（§24 A/B） | feat | — | 中 | ✅ 已完成（待真机验证） | 方案 A：名称列限宽 42%（max 480px）+ 元数据列从名称右侧延伸到状态徽标左侧；Column 改为两个独立 Text 水平排列 |
| T12 | UI：列头排序回归（§27） | feat | T11 | 中 | ✅ 已完成（2026-10-14 裁决，待真机验证） | 资源管理器式列头：`GamesPage.qml` 新增 `SortHead` 组件（悬停底色 + 升/降箭头，点击 `bridge.setSort(key)` 与 models.py 既有列头语义一致）；`ListView.OverlayHeader` 需显式 `width: gameList.width`（否则 header 宽 0），首行下移 33px 防遮挡；DXVK 列经隐形占位链（chipPH/detailPH/folderPH）与状态徽标精确对齐；离屏几何探测 + 渲染截图双验证 |
| T13 | UI：配置页信息模型重构（§33） | feat | — | 高 | ✅ Phase 1 已完成 / Phase 2 进行中 | Phase 1 Python 数据层已建：ConfigListModel 新增 `modifiedCount`/`modifiedSummary`/`resetOption`；bridge 暴露 `modifiedSummary()`/`resetOption(key)`；Phase 2 QML「已改清单」面板已落于 `ConfigPage.qml`，待真机显示环境验证 |
| T14 | UI：注释开关入配置页（§29） | feat | — | 低 | ✅ 已完成（2026-10-14 裁决） | 候选 A + 方案 ①：预览栏「带注释」开关（`ConfigPage.qml` DarkSwitch + `conf_comments` 设置键），与设置页原开关共用同一键；SettingsPage 判断放宽为 `!== false` 与 Python 默认 True 对齐；标题绑定控件行左缘 + elide，杜绝英文长文案重叠 |
| T15 | 英文版 i18n（§28） | feat | — | 高 | ✅ 已完成（2026-10-14 裁决：全量落地，待真机验证） | 路线 A（qsTr/lupdate/lrelease）：8 个 QML 上下文 + bridge 71 处 tr() + GameListModel `_tr()`；`assets/i18n/app_en.ts/.qm` 236 条全译；设置页「界面语言」卡片（`ui_lang`，重启生效）；选项说明语言独立（confkit `_en` 后缀字段）、预设名保持逻辑键不译、SLANG 搜索别名为数据不译；英文离屏四页渲染验证（分组头/状态徽章/版本类别徽章均已随语言切换），修复预览栏标题重叠与「版本更新」徽章漏译；维护工具 `tests/i18n_fill.py`（词条回填）+ `tests/i18n_probe.py`（抽查+渲染） |
| T16 | 作者身份改写（公开前） | chore | — | 低 | ✅ 已完成 | git-filter-repo 改写 77 个提交：`agent@local` → `Janlhin <72262030+Janlhin@users.noreply.github.com>`；备份在 `dxvk-version-manager-py-backup-20261009-182318`；本地 git config 已设；重写后历史已在远端（2026-10-14 常规推送 `7030660..18f19ac` 确认 origin 即改写后基线，无需 force push） |
| T17 | node-app / web-configurator 处置 | chore | — | 低 | ✅ 已完成（2026-10-14 裁决） | **明确排除出仓库**（许可隔离依 PLAN.md §30 / DECISIONS.md「2026-10-09 仓库结构与接手基线」）；2026-10-14 迁移精简时已删除 `D:\Projects\DXVK_Manager` 下的两份副本（伞形库提交 `e7de9b8`，删除前与 C 盘正本逐字节比对一致），正本保留在 C 盘源目录；伞形库根 `.gitignore` 排除 `/node-app/`、`/web-configurator/` 防再入库 |
| T18 | 核心层测试覆盖率（build/model/parse round-trip） | test | — | 中 | ✅ 已建（本次） | `tests/test_build.py` 15 例全绿；纳入 `verify` 门禁；push 后 CI 跑绿 |
| T19 | pyright 门禁修复（消除动态库假阳性 error） | chore | T9 | 低 | ✅ 已完成 | 排除 GUI 测试脚本（`qml_smoke.py`/`render_pages.py`）出类型门禁；`bridge.py` 的 `Signal("QVariantList"/"QVariantMap")` 加 `reportArgumentType` ignore；`covers.py` 文件级放宽 `reportOptionalMemberAccess`（Pillow 可选且无 stub）；pyright 现 **0 errors** |
| T20 | **整体重写：编译语言 + 从零 I18N（终极形态评估）** | refactor | — | 特大 | 待裁决（**最核心长线项**） | 语言候选 Go / Rust / C++ / C# / TypeScript；PS7 定位为编排层、不作重写主体；i18n 自首日起为架构约束而非事后补丁；裁决点与可复用资产见下方附注 |
| T21 | 配置页文档角标 + 提示卡排版重构（§34） | feat | — | 中 | ✅ 已完成（2026-10-15） | 选项行 label 右侧 ⓘ 角标 → 可滚动文档卡：说明/示例/DXVK 原文三区、示例与原文等宽暗底代码块、高度封顶 70%、✕ 与点击外部关闭；`ConfigListModel` 选项行新增 `doc` role（`OptionGroup.doc_parts()`）；悬停 DarkTip 保留显示中文摘要；`fab210c` 补修代码块高度塌陷（TextEdit 溢出压住下一节） |
| T22 | README / THIRD_PARTY_NOTICES 措辞批改 | docs | — | 低 | ✅ 已完成（2026-10-15） | 「Python 重写版」→「独立实现，未复制任何第三方代码；功能设计参考其行为」（THIRD_PARTY_NOTICES §3 同步）；删过时的「未实现：封面图显示」；「两类文件」→ 补 dxvk.conf 与伴生文件；界面表补设置页新卡片、游戏墙三段分组、ⓘ 文档角标；「本机 py -3.13」→「于 Python 3.13 验证」、命令统一 `py -3`；开头依赖去重；《用 AI 做项目》书名引用改为指向 AGENTS.md |
| T23 | 平台标签 i18n（米哈游 / 手动添加） | fix | — | 低 | ✅ 已完成（2026-10-15，待真机英文验证） | `models.py` 行数据与筛选 chip 的 platformLabel 均过 `_tr`；`i18n_fill.py` GAME_LIST_MODEL 补 10 个平台名 + 「全部」共 11 词条；管线重跑 290 条全译；新增 4 个模型测试（翻译/原始键/筛选/过滤）；QML 配色与详情弹窗改走原始 platform key（顺带修复米哈游/Battle.net 平台色从未命中的老问题）；英文探测 0 failures |
| T24 | 版本库元数据补全（CLI 下载路径） | fix | — | 低 | ✅ 已完成（2026-10-15，待真机复验 date/size） | 根因：GitHub API 限流时 jsDelivr 兜底写入的缓存无 date/size，6h TTL 内详情面板恒显 "-"（本机缓存 95 条全空实证）。修复：① `cache_releases` 写入时合并旧缓存已知的 date/size（兜底列表不再擦除元数据）；② `download_release` 成功后 `_note_download` 把真实归档体积写回缓存条目，列表仍缺元数据时标记 stale 促下次刷新；③ jsDelivr 路径追加 atom feed 日期回填（覆盖最新约 10 个版本）。CLI 与 UI 下载路径同时覆盖。新增 4 个缓存测试。「尚未下载」之谜结案：旧 Tk UI 空态文案（提交 2a117ce 已删），截图来自旧进程，现行 QML 无此串 |
| T25 | 界面语言热切换（ui_lang 免重启） | feat | — | 中 | ✅ 已完成（2026-10-15） | 原 T20 列出的「已知欠账」。实现：① `app_qml.set_language(lang)` 运行时换翻译器（模块级持 `_current_translator` 与 `_engine`），装/卸后 `engine.retranslate()` 刷新全部 QML `qsTr` 绑定（实测单纯增减翻译器不会自动刷新，必须显式 retranslate）；② `GameListModel.retranslate()` 重建 Python 侧已解析字符串——平台标签（存 `platformLabelSrc` 源串）+ 状态徽章（行内存原始 `GameStatus` 于 `_status`，`_status_tuple` 复用）；③ `bridge.setSetting` 在 `ui_lang` 变更时调 `_apply_language`：换翻译器 + `model.retranslate()` + 重译 `_config_target_name` 并发 `configTargetChanged` + 发 `languageChanged`；④ `GamesPage` 接 `onLanguageChanged` 重拉 `platformOptions`/`dxtkCounts` 刷新筛选栏；⑤ 扫描 worker 改为传原始 `GameStatus`，`_apply_statuses` 内部用 `status_for` 重算（为热切换铺路）；⑥ 配置说明文案（docs_language）刻意不随 ui_lang 切换。设置页提示改「切换后立即生效」。新增 3 个 retranslate 单测；`i18n_probe` 加运行时热切换断言；实测 QML qsTr 双向刷新正常 |

| T26 | Epic 扫描器改用 EGL v2 权威清单 | fix | — | 中 | ✅ 已完成（2026-10-15） | 根因：原 `scan_epic_games()` 只读 `ProgramData\Epic\EpicGamesLauncher\Data\Manifests\*.item`（EOS 路径，无游戏清单，本机该目录不存在）→ 7 个 Epic 游戏全漏。真机取证：本机 Epic 为 EGL v2，数据在 `com.epicgames.eglv2`（注册表 `Software\Epic Games\EpicGamesLauncher` 的 `AppDataPath` 指向）；权威清单 `installations.jsonl`（每行含 `dir`/`namespace`/`complete`，首行 header 无 dir），显示名靠 `cache\prod\catalog-cache.json` 按 `namespace` 反查 `item.title`。改动：新增 `_egl_data_root`/`_epic_installations`/`_epic_catalog_titles`/`_epic_legacy_manifests`；`scan_epic_games()` 默认走权威清单（跳过 header、丢弃盘上缺失目录、同目录合并取已装条目、namespace→标题做显示名），旧 `.item` 目录作兜底。实测：本机 7 个（3 out of 10 EP1–5、Alan Wake Remastered、Control）全识别且名称正确。门禁：launcher 测试 +2（installations.jsonl 解析、无 catalog 回退文件夹名）。commit `5547199`，push `161be03..5547199` |
| T27 | WeGame 扫描器改盘扫 rail_apps | fix | — | 中 | ✅ 已完成（2026-10-15） | 根因：原 `scan_wegame_games()` 只读 `HKCU\Software\Tencent` 且要求 `InstallLocation`+`DisplayName` 并存；三角洲（Delta Force）注册表在 `HKCU\Software\Rail\Dfmclient-Win64-Test` 仅 `InstallPath` 且键名不符 → 漏掉，只剩无畏契约命中。真机取证：WeGame 权威清单在盘上 `D:\WeGameApps\rail_apps\`，每游戏一个 `Name(appid)` 文件夹（`DeltaForce(2001918)`/`无畏契约(2001715)`）；中文名可靠来源是目录内 `<显示名>卸载.exe`（三角洲行动卸载.exe → 「三角洲行动」）。改动：新增 `_wegame_apps_roots`（探测 C:/D:/E:/F: 的 `WeGameApps\rail_apps` 与 `rail_apps`）、`_wegame_display_name`（优先卸载程序名、回退文件夹名）、`_wegame_games_from_rail_apps`（解析 `Name(appid)`）、`_rail_apps_game_id`（按 rail id 去重）；`scan_wegame_games()` 改为盘扫为主源、注册表 `Software\Tencent` 兜底，按 `(id)` 合并避免无畏契约「根目录」与「`\live` 子目录」重复。实测：返回 2 个（三角洲行动 2001918、无畏契约 2001715），无重复、中文名正确。门禁：launcher 测试 +3（中文名提取、无卸载程序回退、注册表子目录去重）；整套 104 全绿。commit `53fef36`，push `5547199..53fef36` |

## T20 附注：编译语言重写 + 从零 I18N

**定位**：PySide6 版功能待办清零、界面稳定后的终极形态选项。承接 DECISIONS.md
「2026-09-13 架构决策：暂不换前端」——该决策明确「等功能待办清完、界面不再大改后再评估重构」，
本项即该评估的正式立项，**非近期工程**，标记待裁决挂起直至触发条件满足。

### 裁决点（启动前须逐项拍板）

1. **语言与 UI 栈**（初步对比，届时以原型验证为准）：
   - **C#**（Avalonia / WPF）——Windows 单平台最顺，GUI 生态与本地化资源体系（resx）成熟；
   - **Rust**（Slint / egui / Tauri）——内存安全 + 单文件分发；Slint 自带翻译体系，GUI 生态较新；
   - **Go**（Wails / Fyne / Qt bindings）——构建与分发最简，GUI 绑定层质量参差；
   - **C++ / Qt**——自 PySide6 迁移最平缓（QML 可大量直接复用），代价是内存安全与开发效率；
   - **TypeScript**（Electron 或 Tauri 壳；样式层 SCSS 与语言裁决正交，web 系 UI 均可用）——
     **原版 dxvk-manager 蓝本即 TS/Electron（node-app），本领域可行性有实证**；i18n 生态全候选最成熟
     （i18next / FormatJS：键名编译期类型检查、ICU 复数、语言热切换、伪本地化插件），与从零 i18n
     基线严丝合缝；代价：Electron 分发重（百 MB 级），Tauri 轻但壳需 Rust。许可注意：node-app 为
     MIT，重写借鉴其代码保留版权声明即合法；web-configurator 为 GPL-3.0，仍只能参照交互、不可复制代码；
   - **PowerShell 7 —— 不作重写主体**：GUI 无成熟出路（WPF 互操作仅 Windows，无 Avalonia 级方案）、
     脚本分发易被 AV 误报，i18n 仅 `Import-LocalizedData` 错误消息级机制（无复数/ICU/RTL）。
     其正确定位：**入口与编排层**（启动/诊断/verify 已是 PS1，维持现状），另可选伴生交付
     「PS7 模块 CLI 前端」（扫描/安装/还原命令化，供自动化场景），属增量交付、不计入重写。
2. **重写范围**：整体重写 vs 核心层先行移植（`parse`/`build`/`validate`/`sources` 为纯标准库逻辑，与 UI 完全解耦，可独立先行）。
3. **时机**：T13 收尾、真机验证清单清零后启动评估；与 bridge 拆分议题合并考虑。

### 从零 I18N 基线（T15 的经验前置为架构约束）

- **源语言不硬编码**：源串即键或独立键名，文案全部外置——T15 的 71 处 tr() 逐文件补包、3 处漏译返工，即「事后 i18n」的代价实证；
- **词条校验进 CI**：缺失/漏译 key 直接红（`tests/i18n_fill.py` 逐键断言思路升格为门禁）；
- **复数 / 占位符 / 日期数字走 CLDR**，禁止拼接串；预留 RTL；**语言热切换**（已于 T25 实现：`ui_lang` 免重启，换翻译器后 `engine.retranslate()` 刷新 QML + `GameListModel.retranslate()` 重建模型字符串）；
- **伪本地化测试**：拉长串 + 变音符暴露布局硬编码（T14 预览栏标题重叠即此类缺陷）；
- **逻辑键与展示文案分离**：预设名/模式名不得作为逻辑判断依据（对应「性能优先/纯净」不译的权宜之计）。

### 可复用资产

`confspec`/`curate` 的 dxvk.conf 知识库与 PURPOSE 数据、SLANG 别名表、设置/账本 schema、
现有测试用例语义均可直接导出；QML 界面结构（若最终选 Qt 系）可参照移植；
node-app 的扫描/版本管理流程语义与 web-configurator 的 dxvk.conf 配置交互设计可作产品参照
（代码均不复制，许可边界见裁决点 1）。

> 可执行项（状态非「待裁决」）≥ 3，满足阶段 3 退出判据。待裁决项占多数属接手期正常现象，
> 不得为压低阻塞指标而擅设默认。
