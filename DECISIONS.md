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
- 理由：核心层已可 100% 复用，等功能待办清完、界面不再大改后再评估重构（见 `TASKS.md` 的 bridge 拆分）。
