# 设计规范（DESIGN.md）

界面不再靠感觉调，全部取自公开设计规范的数值。

## 圆角：对齐 Fluent 的 token 标度

来源：Fluent UI 的 `borderRadius` token
（`packages/tokens/src/global/borderRadius.ts`）
原值：`none 0 / small 2 / medium 4 / large 6 / xLarge 8 / 2xLarge 12 / 3xLarge 16`

本项目采用其中四档，每档只负责一类元素：

| token | 值 | 用途 |
| --- | --- | --- |
| `radiusMicro` | 4 | 复选框、徽标、缩略图、滚动条滑块 |
| `radiusControl` | 4 | 按钮、输入框、下拉框、筛选标签 |
| `radiusCard` | 8 | 卡片、列表面板 |
| `radiusPanel` | 12 | 对话框、大块面板 |
| `radiusHairline` | 1 | 2px 指示条（标签页下划线） |

规则：**全项目不允许出现硬编码圆角**（审计脚本：`radius:\s*[0-9]` 应为 0 处）。

## 间距：4px 基准栅格

统一为 4 / 8 / 12 / 16 / 24 / 32，全部内边距、外边距、间距只取这些值：

| token | 值 |
| --- | --- |
| `space1` | 4 |
| `space2` | 8 |
| `space3` | 12 |
| `space4` | 16 |
| `space5` | 24 |
| `space6` | 32 |
| `pad` | 16（页面通用内边距） |

## 字号

| token | 值 | 用途 |
| --- | --- | --- |
| `fontMicro` | 10 | 角标、单位 |
| `fontCaption` | 11 | 说明文字、辅助信息 |
| `fontBody` | 13 | 正文、选项名 |
| `fontTitle` | 15 | 小节标题 |
| `fontHeading` | 18 | 页面标题 |

## 深色配色与控件

* 三层表面：`bg #141619`（底）→ `surface #1b1e23`（卡片/工具栏）→ `surfaceAlt #20242b`（输入框/表头）
* 描边：`border #2c313a`，交互态 `borderStrong #3a4150`
* 文字三级：`text #e7e9ec` / `textMuted #98a2b3`（说明文字）/ `textDim #6f7885`（最次要）
* 实心按钮：`primary #33549f` + `primaryText #e6ecfb`（不用亮蓝，避免在深色里刺眼）
* **应用级深色调色板**（`_dark_palette()`）：Tooltip、下拉弹层等 Qt 自绘控件跟随深色，不再出现白框
* 复选框：16px、4px 圆角、深底 + 勾选态用主色，替代默认的大白方块

## 布局模式

* **设置行（配置页）**：左侧 名称（13px 加粗）+ 中文说明（11px 次要色），右侧控件贴齐列表右边缘；行悬停高亮。参照 Fluent SettingsCard / VS Code 设置页。
* **列表行（游戏/版本）**：紧凑左对齐信息组，操作按钮紧跟其后，**不用 `fillWidth` 把按钮顶到窗口最右**（1920px 宽时按钮会与内容失去关联）。
* **卡片墙**：列数按可用宽度计算，**余数均摊到列间距**，避免右侧死区；卡片在各自格子内居中。
* **滚动**：每格滚轮约 1.8 行（卡片）/ 3 行（列表），并保留触控板像素滚动。
