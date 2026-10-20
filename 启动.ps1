#Requires -Version 5.1
<#
    DXVK Version Manager (Python) —— 启动器
    由 启动.bat 移植为 PowerShell，行为保持一致：
      选 Python → 备 .venv → 装 PySide6/Pillow → 启动 main.py（日志落盘，出错不闪退）

    用法：
      pwsh -NoProfile -ExecutionPolicy Bypass -File .\启动.ps1
#>

$ErrorActionPreference = 'Continue'

# ---------- 0. 环境：控制台与子进程统一 UTF-8 ----------
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
try { $OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$env:PYTHONIOENCODING = 'utf-8'
Set-Location -LiteralPath $PSScriptRoot
try { $Host.UI.RawUI.WindowTitle = 'DXVK Version Manager (Python)' } catch { }

$InstallLog = Join-Path $PSScriptRoot '安装日志.txt'
$LaunchLog  = Join-Path $PSScriptRoot '启动日志.txt'
$VenvPy     = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

# ---------- 小工具 ----------
function Invoke-Logged {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [string[]]$ArgList = @(),
        [Parameter(Mandatory = $true)][string]$LogFile,
        [switch]$Append
    )
    & $Exe @ArgList 2>&1 | Out-File -FilePath $LogFile -Encoding utf8 -Append:$Append
    return $LASTEXITCODE
}

function Show-LogTail {
    param([string]$Path, [int]$Lines = 30)
    if (Test-Path -LiteralPath $Path) {
        Write-Host '============================================'
        Get-Content -LiteralPath $Path -Encoding utf8 -Tail $Lines
        Write-Host '============================================'
    }
}

# Python 统一表示为「可执行文件 + 版本前缀参数」，例如 py + -3.13
function Test-Python {
    param([string]$Exe, [string[]]$Pre = @())
    if (-not (Get-Command $Exe -ErrorAction SilentlyContinue)) { return $false }
    $probe = @() + $Pre + @('-c', 'import sys')
    & $Exe @probe 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}

# ---------- 1. 选择真实可用的 Python ----------
$PyExe = $null
$PyPre = @()

if (Test-Path -LiteralPath $VenvPy) {
    $PyExe = $VenvPy
    $PyPre = @()
}
else {
    $candidates = @(
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
}

if (-not $PyExe) {
    Write-Host '[错误] 未找到 Python 3.10 或更高版本。'
    Write-Host '请到 https://www.python.org/downloads 安装，并勾选 "Add python.exe to PATH"。'
    Write-Host '安装完成后重新运行本脚本。'
    Write-Host ''
    Read-Host '按回车键退出'
    exit 1
}

$shown = if ($PyPre.Count) { "$PyExe $($PyPre -join ' ')" } else { $PyExe }
Write-Host "使用 Python：$shown"

# ---------- 2. 准备本地虚拟环境（避开 externally-managed 限制）----------
if (-not (Test-Path -LiteralPath $VenvPy)) {
    Write-Host ''
    Write-Host '[准备] 创建本地虚拟环境 .venv（首次，约几秒）...'
    Invoke-Logged -Exe $PyExe -ArgList (@() + $PyPre + @('-m', 'venv', '.venv')) -LogFile $InstallLog -Append | Out-Null
    if (-not (Test-Path -LiteralPath $VenvPy)) {
        Write-Host ''
        Write-Host '[错误] 创建虚拟环境失败，详情见 安装日志.txt：'
        Show-LogTail -Path $InstallLog
        Read-Host '按回车键退出'
        exit 1
    }
}
Write-Host "使用环境：$VenvPy"

# ---------- 3. 在虚拟环境内安装依赖 ----------
& $VenvPy -c 'import PySide6' 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '[准备] 安装图形界面依赖 PySide6 + Pillow（首次需联网，约 1-2 分钟，勿关窗口）...'
    Invoke-Logged -Exe $VenvPy -ArgList @('-m', 'pip', 'install', '--upgrade', 'pip') -LogFile $InstallLog -Append | Out-Null
    $code = Invoke-Logged -Exe $VenvPy -ArgList @('-m', 'pip', 'install', 'PySide6', 'Pillow') -LogFile $InstallLog -Append
    if ($code -ne 0) {
        Write-Host ''
        Write-Host '[错误] 依赖安装失败，多为网络/代理问题。详情见 安装日志.txt：'
        Show-LogTail -Path $InstallLog
        Write-Host '把上方内容或 安装日志.txt 发我。'
        Write-Host ''
        Read-Host '按回车键退出'
        exit 1
    }
    Write-Host '[完成] 依赖已安装。'
}

# ---------- 4. 启动（输出写日志，出错不闪退）----------
Write-Host '正在启动 DXVK Version Manager ...'
Write-Host "日志写入：$LaunchLog"

$runArgs = @('main.py') + @($args)
$code = Invoke-Logged -Exe $VenvPy -ArgList $runArgs -LogFile $LaunchLog
if ($code -ne 0) {
    Write-Host ''
    Write-Host "[异常退出 退出码 $code] 最近错误："
    Show-LogTail -Path $LaunchLog
    Write-Host '把上方内容或 启动日志.txt 发我。'
    Write-Host ''
    Read-Host '按回车键退出'
    exit $code
}
