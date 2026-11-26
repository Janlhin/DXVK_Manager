# 贡献指南

DXVK Version Manager（Python 版）是 Windows 桌面工具：核心层与 CLI 纯标准库，图形界面用
PySide6，封面用 Pillow。工程约束见 [AGENTS.md](AGENTS.md)。

## 环境准备

- Python 3.10+（CI 在 3.13 上验证）。
- 安装开发期依赖（ruff / pyright / pytest）：

```powershell
python -m pip install -r requirements-dev.txt
```

图形界面与封面依赖（PySide6 / Pillow）见 `requirements.txt`；不装也能跑核心层与命令行，
模型相关测试在缺 PySide6 时自动跳过。

## 本地验收

本地与 CI 共用唯一验收入口：

```powershell
# Windows
.\verify.ps1

# Linux / CI
bash verify.sh
```

`verify` 依次执行：`ruff`（零告警）→ `pyright`（0 errors）→ `pytest tests`（全量核心套件）
→ QML 结构与词条基线 → i18n 词库一致性 → 配置层金标准。

只跑测试也可以：

```powershell
python -m pytest tests -q
```

GUI 冒烟测试 `tests/qml_smoke.py` 需要显示环境，不在无显示 CI 的必过门禁内；改动界面后
请在本机手动运行。

## 代码与文档位置

- `dxvk_toolkit/` — 核心层（confkit 配置核心、standalone 独立配置器、ui 界面与 bridge）。
- `tests/` — pytest 套件、金标准与基线数据。
- `docs/` — 审计与设计资料，索引见 [docs/README.md](docs/README.md)。
- 第三方来源登记见 [MANIFEST.md](MANIFEST.md)；致谢与许可边界见
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 提交规范

- 一个 commit 只做一件事（原子提交）；提交信息用 Conventional Commits
  （`feat:`/`fix:`/`docs:`/`refactor:`/`chore:`/`test:`），正文写“为什么”。
- 重构与行为变更拆成两个提交；每个提交自身须能通过 `verify`。
- 先改文档再改代码（或同一提交内），见 AGENTS.md「文档先行」。

## PR 要求

- PR 说明改动动机、影响面；本地先跑通 `verify`（或在 CI 结论里如实标注未跑项）。
- 不引入运行时新的第三方依赖；工具链依赖进 `requirements-dev.txt`。
