# 唯一验收入口（Windows 本地）。GUI 测试 qml_smoke.py 需要显示环境，不在必过门禁内。
$ErrorActionPreference = 'Stop'
Write-Host '== pytest: 核心 + 金标准 + 边界校验（纯标准库套件）=='
py -3 -m pytest tests/test_core.py tests/test_conf_golden.py tests/test_validate.py -q
Write-Host 'verify: tests OK'
