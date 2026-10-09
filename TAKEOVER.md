= TAKEOVER.md — 接手报告（2026-10-09）

按《用 AI 做项目：接手未完成项目规范》完成阶段 0–2（只读盘点 + 真伪验证 + 差距评估）。
阶段 0–2 未改动任何代码；本文件与基线提交同批入库。

== 0. 项目身份

- 名称：DXVK Version Manager（Python 版）｜仓库：`python-app/dxvk-version-manager-py`｜远端：私有 `github.com/Janlhin/DXVK_Manager`
- 接手时 HEAD：`e37991b`｜提交数：62｜分支：`master`
- 同文件夹另有 `node-app`（Electron/MIT 克隆）、`web-configurator`（GPL-3.0 克隆），均未入库。
- **结构异常**：工作区上层 `C:/Users/Janlhin/.git`（HOME 仓库）遮蔽本仓库，plain `git` 从工作区会命中 HOME 仓库。

== 1. 技术栈（来源：源码 import / lockfile）

- python-app：Python 3.10+；核心层纯标准库；GUI 用 PySide6（9 文件），封面用 Pillow（4 文件）。**无依赖清单**。
- node-app：Electron 42 + tar，有 `package-lock.json`，无 `node_modules`。
- web-configurator：纯 HTML/CSS/JS，无构建。

== 2. 真伪对照表

[cols="1,1,2,2,1",options="header"]
|===
| 声称 | 来源 | 验证证据 | 实际结果 | 判定

| 已推送 GitHub（私有，58 commits） | PLAN §30 | `git log`/`remote` | 远端正确私有；本地 62 commits（瘦身后新增）；分支仍 `master` | 部分真
| 测试全绿（核心21/金标准/烟雾） | PLAN §0/§30 | 沙箱 `pytest` | 沙箱无 PySide6/pytest 且 PyPI 不可达；目标为 Windows 桌面 | 未验证→待裁决
| python-app 纯标准库零 pip 依赖 | README | `grep PySide6/Pillow` | confkit 纯 stdlib；GUI 需 PySide6、covers 需 Pillow，均未声明 | 部分真
| node-app 可 `npm install && build` | node-app README | 沙箱 `npm ci` | 无 node_modules、无网络；第三方克隆非活跃 | 未验证→待裁决
| web-configurator 静态站无构建 | README | 读文件 | 纯 HTML/JS/CSS，无 package.json | 真
| README 内容准确 | PLAN §30.2 自陈 | 读 README | 项目自认过期（写两页/基础高级） | 假（已知差距）
| dxvk-manager 受版本控制 | 接手假设 | `git rev-parse --show-toplevel` | 解析到 HOME/.git（0 tracked） | 假（结构异常）
| 无构建产物/凭据入库 | PLAN §30 | `git ls-files \| grep zip/node_modules` | 未跟踪 zip/node_modules；但无 MANIFEST 登记来源 | 部分真
|===

== 3. 差距清单（对照《强制工程校验方案》强制条款）

[cols="1,2,1,2",options="header"]
|===
| 主规范条款 | 现状 | 差距 | 修复成本

| 文档先行四文件 | 仅 README.md + dev 文档；无 AGENTS/DECISIONS/MANIFEST | 缺 3 个 | 中（本次基线补齐）
| `verify` 唯一验收入口 | 无 | 缺失 | 高（本次基线建）
| Git + Conventional Commits + commitlint | 约定式提交但无 commitlint 门禁 | 缺门禁 | 低（本次加 CI）
| 类型系统 / Lint | node-app 有 ESLint；python-app 无任何 lint | python-app 缺 | 中
| 测试 + 覆盖率阈值 | pytest 测试但无 CI 跑、无覆盖率门槛 | 缺 CI 测试 | 高（本次加 CI）
| CI 权威判定 | node-app 有 workflow 但不跑测试；python-app 无 CI | python-app 缺 | 高（本次加）
| 运行时边界 schema | 无 | 缺 | 中
| 死代码治理 knip/jscpd | 自陈 bridge 上帝对象/死代码；无工具 | 缺 | 中
| 删除分级授权 | 未成文 | 缺（本次写入 AGENTS.md） | 低
|===

== 4. 风险

- R1（高危）HOME/.git 遮蔽项目，plain `git` 误操作家目录风险。
- R2（中危）测试不可在本沙箱验证，需用户 Windows 本机（装 PySide6/Pillow）跑 `pytest tests/` + `qml_smoke.py`。
- R3（中危）PySide6/Pillow 未在任何清单声明，复现性靠用户自装。
- R4（低危）历史提交作者为 `agent@local`，公开前需改写（PLAN §30.3）。

== 5. 待裁决项（不可设默认）

- D1 仓库结构：已决——以 python-app 为准，node-app/web-configurator 不入库。
- D2 测试验证环境：本沙箱无法验证，需用户 Windows 本机。
- D3 UI backlog（全部「待你定」）：§22/§24/§25/§27/§29/§33/§26/§28，见 `TASKS.md`。
- D4 HOME/.git 是否意外创建：用户选择「先别动」。
- D5 作者身份改写时机：公开前。

== 6. 下一步

进入 `TASKS.md` 推进循环；首批：T1–T4（基线工程）本次提交完成，T5 起为后续。
