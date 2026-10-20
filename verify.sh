#!/usr/bin/env bash
# 唯一验收入口（CI 与本地共用）。GUI 冒烟 qml_smoke.py 需要显示环境，不在必过门禁内。
set -euo pipefail
echo "== ruff: 静态检查（零警告）=="
python -m ruff check .
echo "== pyright: 类型检查（basic 模式，门禁为 0 errors）=="
# 不加 --warnings：该旗标语义是「有 warning 即 exit 1」，而 Linux runner 未装
# PySide6/PIL 必产生 import warning，导致 CI 恒红（2026-10-14 修复）。
python -m pyright
echo "== pytest: 全量核心套件（无 PySide6 时模型测试自动跳过）=="
python -m pytest tests -q
echo "== qml: 静态结构与词条基线（纯标准库）=="
python tests/qml_check.py
echo "== i18n: 英文词库与源码一致（纯标准库）=="
# 词库必须与源码同步：QML 拆分会让 qsTr 的 context 改名，漏了就静默留中文。
python tests/i18n_fill.py --check
echo "== golden: 配置层金标准（逐字节比对）=="
python tests/test_conf_golden.py
echo "verify: ruff + pyright + tests + qml + i18n + golden OK"
