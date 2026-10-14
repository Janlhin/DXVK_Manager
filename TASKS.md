# TASKS.md — 任务队列（由差距清单转化）

字段：ID · 标题 · 类型 · 依赖 · 规模 · 状态 · 验收/下一步。
「待裁决」项须用户拍板后方可开工（见 `TAKEOVER.md` D3）。

| ID | 标题 | 类型 | 依赖 | 规模 | 状态 | 验收 / 下一步 |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | `verify` 聚合脚本（pytest stdlib 套件） | chore | — | 低 | ✅ 已建（本次基线） | `.\verify.ps1` 退出 0 |
| T2 | 四个文档（README/AGENTS/DECISIONS/MANIFEST）+ 接手报告 | docs | — | 中 | ✅ 已建（本次基线） | 结构校验通过 |
| T3 | CI 跑测试 + lint + commitlint | ci | T1 | 高 | ✅ 已建（本次基线） | push 后 GitHub Actions 全绿 |
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
| T16 | 作者身份改写（公开前） | chore | — | 低 | ✅ 已完成 | git-filter-repo 改写 77 个提交：`agent@local` → `Janlhin <72262030+Janlhin@users.noreply.github.com>`；备份在 `dxvk-version-manager-py-backup-20261009-182318`；本地 git config 已设；待 force push（需 token 刷新） |
| T17 | node-app / web-configurator 处置 | chore | — | 低 | ✅ 已完成（2026-10-14 裁决） | **明确排除出仓库**（许可隔离依 PLAN.md §30 / DECISIONS.md「2026-10-09 仓库结构与接手基线」）；2026-10-14 迁移精简时已删除 `D:\Projects\DXVK_Manager` 下的两份副本（伞形库提交 `e7de9b8`，删除前与 C 盘正本逐字节比对一致），正本保留在 C 盘源目录；伞形库根 `.gitignore` 排除 `/node-app/`、`/web-configurator/` 防再入库 |
| T18 | 核心层测试覆盖率（build/model/parse round-trip） | test | — | 中 | ✅ 已建（本次） | `tests/test_build.py` 15 例全绿；纳入 `verify` 门禁；push 后 CI 跑绿 |
| T19 | pyright 门禁修复（消除动态库假阳性 error） | chore | T9 | 低 | ✅ 已完成 | 排除 GUI 测试脚本（`qml_smoke.py`/`render_pages.py`）出类型门禁；`bridge.py` 的 `Signal("QVariantList"/"QVariantMap")` 加 `reportArgumentType` ignore；`covers.py` 文件级放宽 `reportOptionalMemberAccess`（Pillow 可选且无 stub）；pyright 现 **0 errors** |

> 可执行项（状态非「待裁决」）≥ 3，满足阶段 3 退出判据。待裁决项占多数属接手期正常现象，
> 不得为压低阻塞指标而擅设默认。
