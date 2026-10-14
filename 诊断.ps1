#Requires -Version 5.1
<#
    DXVK 启动诊断 —— 由 诊断.bat 移植
    生成 诊断日志.txt 并回显结果。

    用法：
      pwsh -NoProfile -ExecutionPolicy Bypass -File .\诊断.ps1
#>

$ErrorActionPreference = 'Continue'

# ---------- 0. 环境：控制台与子进程统一 UTF-8 ----------
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
try { $OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$env:PYTHONIOENCODING = 'utf-8'
Set-Location -LiteralPath $PSScriptRoot
try { $Host.UI.RawUI.WindowTitle = 'DXVK 启动诊断' } catch { }

$DiagLog = Join-Path $PSScriptRoot '诊断日志.txt'

# Python 统一表示为「可执行文件 + 版本前缀参数」，例如 py + -3.13
function Test-Python {
    param([string]$Exe, [string[]]$Pre = @())
    if (-not (Get-Command $Exe -ErrorAction SilentlyContinue)) { return $false }
    $probe = @() + $Pre + @('-c', 'import sys')
    & $Exe @probe 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Invoke-Logged {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [string[]]$ArgList = @(),
        [Parameter(Mandatory = $true)][string]$LogFile
    )
    & $Exe @ArgList 2>&1 | Out-File -FilePath $LogFile -Encoding utf8
    return $LASTEXITCODE
}

# ---------- 1. 选择真实可用的 Python（与原 BAT 一致：用系统 Python，不走 .venv）----------
$PyExe = $null
$PyPre = @()

$candidates = @(
    @{ Exe = 'C:\Users\Janlhin\.local\bin\python.exe';                                  Pre = @() },
    @{ Exe = 'C:\Users\Janlhin\.workbuddy\binaries\python\versions\3.13.12\python.exe'; Pre = @() },
    @{ Exe = 'py';      Pre = @('-3.13') },
    @{ Exe = 'py';      Pre = @('-3.12') },
    @{ Exe = 'py';      Pre = @('-3.11') },
    @{ Exe = 'py';      Pre = @('-3.10') },
    @{ Exe = 'python';  Pre = @() },
    @{ Exe = 'python3'; Pre = @() }
)
foreach ($c in $candidates) {
    if (Test-Python -Exe $c.Exe -Pre $c.Pre) {
        $PyExe = $c.Exe
        $PyPre = @() + $c.Pre
        break
    }
}

if (-not $PyExe) {
    Write-Host '[错误] 未找到 Python。'
    Read-Host '按回车键退出'
    exit 1
}

$shown = if ($PyPre.Count) { "$PyExe $($PyPre -join ' ')" } else { $PyExe }
Write-Host "使用 Python：$shown"

# ---------- 2. 生成诊断日志 ----------
Write-Host '正在生成诊断日志（如需联网安装会一并尝试）...'
Invoke-Logged -Exe $PyExe -ArgList (@() + $PyPre + @('诊断.py')) -LogFile $DiagLog | Out-Null

Write-Host ''
Write-Host '===== 诊断结果 ====='
if (Test-Path -LiteralPath $DiagLog) {
    Get-Content -LiteralPath $DiagLog -Encoding utf8
}
Write-Host ''
Write-Host '（已保存为 诊断日志.txt）'
Read-Host '按回车键退出'
