@echo off
chcp 65001 >nul
setlocal EnableExtensions
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
title DXVK Version Manager (Python)

REM ---- 1. 选择真实可用的 Python ----
set "PY="
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
    goto :found
)
if exist "C:\Users\Janlhin\.local\bin\python.exe" (
    set "PY=C:\Users\Janlhin\.local\bin\python.exe"
    goto :found
)
if exist "C:\Users\Janlhin\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
    set "PY=C:\Users\Janlhin\.workbuddy\binaries\python\versions\3.13.12\python.exe"
    goto :found
)
for %%V in (3.13 3.12 3.11 3.10) do (
    py -%%V -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        set "PY=py -%%V"
        goto :found
    )
)
python -c "import sys" >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
    goto :found
)
python3 -c "import sys" >nul 2>nul
if not errorlevel 1 (
    set "PY=python3"
    goto :found
)

echo [错误] 未找到 Python 3.10 或更高版本。
echo 请到 https://www.python.org/downloads 安装，并勾选 "Add python.exe to PATH"。
echo 安装完成后重新双击本文件。
echo.
pause
exit /b 1

:found
echo 使用 Python：%PY%

REM ---- 2. 准备本地虚拟环境（避开 uv 的 externally-managed 限制）----
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [准备] 创建本地虚拟环境 .venv（首次，约几秒）...
    %PY% -m venv .venv >> 安装日志.txt 2>&1
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo [错误] 创建虚拟环境失败，详情见 安装日志.txt：
        echo ============================================
        powershell -NoProfile -Command "Get-Content -Encoding utf8 -Tail 30 '安装日志.txt'" 2>nul || more "安装日志.txt"
        echo ============================================
        pause
        exit /b 1
    )
)
set "VPY=.venv\Scripts\python.exe"
echo 使用环境：%VPY%

REM ---- 3. 在虚拟环境内安装依赖（不受 externally-managed 限制）----
%VPY% -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo.
    echo [准备] 安装图形界面依赖 PySide6 + Pillow（首次需联网，约 1-2 分钟，勿关窗口）...
    %VPY% -m pip install --upgrade pip >> 安装日志.txt 2>&1
    %VPY% -m pip install PySide6 Pillow >> 安装日志.txt 2>&1
    if errorlevel 1 (
        echo.
        echo [错误] 依赖安装失败，多为网络/代理问题。详情见 安装日志.txt：
        echo ============================================
        powershell -NoProfile -Command "Get-Content -Encoding utf8 -Tail 30 '安装日志.txt'" 2>nul || more "安装日志.txt"
        echo ============================================
        echo 把上方内容或 安装日志.txt 发我。
        echo.
        pause
        exit /b 1
    )
    echo [完成] 依赖已安装。
)

REM ---- 4. 启动（输出写日志，出错不闪退）----
echo 正在启动 DXVK Version Manager ...
echo 日志写入：%CD%\启动日志.txt

%VPY% main.py %* > "启动日志.txt" 2>&1
set "CODE=%errorlevel%"
if not "%CODE%"=="0" (
    echo.
    echo [异常退出 退出码 %CODE%] 最近错误：
    echo ============================================
    powershell -NoProfile -Command "Get-Content -Encoding utf8 -Tail 30 '启动日志.txt'" 2>nul || more "启动日志.txt"
    echo ============================================
    echo 把上方内容或 启动日志.txt 发我。
    echo.
    pause
)
