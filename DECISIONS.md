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

== 2026-09-13 架构决策：暂不换前端

- 决策：核心层（3030 行）与 UI 解耦，保持 PySide6/Qt 前端，换架构（WebView2/Qt 重写）暂缓。
- 理由：核心层已可 100% 复用，等功能待办清完、界面不再大改后再评估重构（见 `TASKS.md` 的 bridge 拆分）。
