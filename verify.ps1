# 唯一验收入口（Windows 本地）。GUI 冒烟 qml_smoke.py 需要显示环境，不在必过门禁内。
#
# 两处 2026-10-20 修复：
#  1) 解释器按 .venv → py -3 → python 依次探测。部分机器上 py 启动器没有注册
#     任何发行版（py -3 直接返回 103），旧脚本因此根本跑不起来。
#  2) 每一步显式检查 $LASTEXITCODE。Windows PowerShell 5.1 不会因为原生命令
#     返回非零而中止（$ErrorActionPreference 只管 cmdlet），旧脚本在
#     ruff/pyright 失败时仍以 0 退出，本地门禁形同虚设。
$ErrorActionPreference = 'Stop'

$PyExe = 'python'
$PyArgs = @()
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython) {
    $PyExe = $venvPython
} else {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $launcher) {
        & py -3 -c 'import sys' 2>$null
        if ($LASTEXITCODE -eq 0) {
            $PyExe = 'py'
            $PyArgs = @('-3')
        }
    }
}
Write-Host ("interpreter: {0} {1}" -f $PyExe, ($PyArgs -join ' '))

function Assert-Step([string]$Label) {
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] $Label" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host '== ruff: 静态检查（零警告）=='
& $PyExe @PyArgs -m ruff check .
Assert-Step 'ruff'

Write-Host '== pyright: 类型检查（basic 模式，门禁为 0 errors）=='
# 不加 --warnings：该旗标语义是「有 warning 即 exit 1」，而 Linux runner 未装
# PySide6/PIL 必产生 import warning，导致 CI 恒红（2026-10-14 修复）。
& $PyExe @PyArgs -m pyright
Assert-Step 'pyright'

Write-Host '== pytest: 全量核心套件（无 PySide6 时模型测试自动跳过）=='
& $PyExe @PyArgs -m pytest tests -q
Assert-Step 'pytest'

Write-Host '== golden: 配置层金标准（逐字节比对）=='
& $PyExe @PyArgs tests/test_conf_golden.py
Assert-Step 'golden'

Write-Host 'verify: ruff + pyright + tests + golden OK'
exit 0