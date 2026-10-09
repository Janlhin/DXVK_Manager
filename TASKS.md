# TASKS.md — 任务队列（由差距清单转化）

字段：ID · 标题 · 类型 · 依赖 · 规模 · 状态 · 验收/下一步。
「待裁决」项须用户拍板后方可开工（见 `TAKEOVER.md` D3）。

| ID | 标题 | 类型 | 依赖 | 规模 | 状态 | 验收 / 下一步 |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | `verify` 聚合脚本（pytest stdlib 套件） | chore | — | 低 | ✅ 已建（本次基线） | `.\verify.ps1` 退出 0 |
| T2 | 四个文档（README/AGENTS/DECISIONS/MANIFEST）+ 接手报告 | docs | — | 中 | ✅ 已建（本次基线） | 结构校验通过 |
| T3 | CI 跑测试 + lint + commitlint | ci | T1 | 高 | ✅ 已建（本次基线） | push 后 GitHub Actions 全绿 |
| T4 | commitlint 提交门禁配置 | chore | — | 低 | ✅ 已建（本次基线） | PR 提交信息符合约定式 |
| T5 | 声明 PySide6/Pillow 运行时依赖清单 | chore | — | 低 | 待做 | `MANIFEST.md` 补精确版本 SHA |
| T6 | 静态检查达标（ruff 零警告） | chore | T3 | 中 | 待做（首跑可能需修） | `ruff check .` 退出 0 |
| T7 | 死代码治理（等价 knip：vulture/ruff unused） | chore | T6 | 中 | 待做 | bridge 上帝对象、GameCard.selected 等清理 |
| T8 | 运行时边界 schema 校验 | feat | — | 中 | 待做 | 配置解析/网络响应/CLI 参数显式校验 |
| T9 | 引入 pyright 类型检查（Python 无编译期类型） | chore | — | 中 | 待做 | `pyright` 接入 verify |
| T10 | UI：封面圆角方案 B（缓存切片） | feat | — | 中 | 待裁决（§22，已选 B 未实现） | 卡片/列表/弹窗圆角像素验证 |
| T11 | UI：列表右侧太空（§24 A/B） | feat | — | 中 | 待裁决 | 用户选 A 或 B |
| T12 | UI：列头排序回归（§27） | feat | T11 | 中 | 待裁决 | 资源管理器式列头 |
| T13 | UI：配置页信息模型重构（§33） | feat | — | 高 | 待裁决 | 场景分组+作用域+已改清单 |
| T14 | UI：注释开关入配置页（§29） | feat | — | 低 | 待裁决 | 配置页直接选 |
| T15 | 英文版 i18n（§28） | feat | — | 高 | 待裁决 | qsTr / 字典路线 |
| T16 | 作者身份改写（公开前） | chore | — | 低 | 待裁决（公开前） | `git filter-repo` 或压初始提交 |
| T17 | node-app / web-configurator 处置 | chore | — | 低 | 待裁决 | 维持外部参考 / 或明确排除 |

> 可执行项（状态非「待裁决」）≥ 3，满足阶段 3 退出判据。待裁决项占多数属接手期正常现象，
> 不得为压低阻塞指标而擅设默认。
