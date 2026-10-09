#!/usr/bin/env bash
# 唯一验收入口（CI 与本地共用）。GUI 测试 qml_smoke.py 需要显示环境，不在必过门禁内。
set -euo pipefail
echo "== ruff: 静态检查（零警告）=="
python -m ruff check .
echo "== pyright: 类型检查（basic 模式）=="
python -m pyright --warnings
echo "== pytest: 核心 + 金标准 + 边界校验 + 构建层（纯标准库套件）=="
python -m pytest tests/test_core.py tests/test_conf_golden.py tests/test_validate.py tests/test_build.py -q
echo "verify: ruff + pyright + tests OK"
