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
| T12 | UI：列头排序回归（§27） | feat | T11 | 中 | 待裁决 | 资源管理器式列头 |
| T13 | UI：配置页信息模型重构（§33） | feat | — | 高 | ✅ Phase 1 已完成 / Phase 2 进行中 | Phase 1 Python 数据层已建：ConfigListModel 新增 `modifiedCount`/`modifiedSummary`/`resetOption`；bridge 暴露 `modifiedSummary()`/`resetOption(key)`；Phase 2 QML「已改清单」面板已落于 `ConfigPage.qml`，待真机显示环境验证 |
| T14 | UI：注释开关入配置页（§29） | feat | — | 低 | 待裁决 | 配置页直接选 |
| T15 | 英文版 i18n（§28） | feat | — | 高 | 待裁决 | qsTr / 字典路线 |
| T16 | 作者身份改写（公开前） | chore | — | 低 | ✅ 已完成 | git-filter-repo 改写 77 个提交：`agent@local` → `Janlhin <72262030+Janlhin@users.noreply.github.com>`；备份在 `dxvk-version-manager-py-backup-20261009-182318`；本地 git config 已设；待 force push（需 token 刷新） |
| T17 | node-app / web-configurator 处置 | chore | — | 低 | 待裁决 | 维持外部参考 / 或明确排除 |
| T18 | 核心层测试覆盖率（build/model/parse round-trip） | test | — | 中 | ✅ 已建（本次） | `tests/test_build.py` 15 例全绿；纳入 `verify` 门禁；push 后 CI 跑绿 |
| T19 | pyright 门禁修复（消除动态库假阳性 error） | chore | T9 | 低 | ✅ 已完成 | 排除 GUI 测试脚本（`qml_smoke.py`/`render_pages.py`）出类型门禁；`bridge.py` 的 `Signal("QVariantList"/"QVariantMap")` 加 `reportArgumentType` ignore；`covers.py` 文件级放宽 `reportOptionalMemberAccess`（Pillow 可选且无 stub）；pyright 现 **0 errors** |

> 可执行项（状态非「待裁决」）≥ 3，满足阶段 3 退出判据。待裁决项占多数属接手期正常现象，
> 不得为压低阻塞指标而擅设默认。
