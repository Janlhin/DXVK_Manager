@echo off
chcp 65001 >nul
setlocal EnableExtensions
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
title DXVK 启动诊断
set "PY="
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
echo [错误] 未找到 Python。
pause
exit /b 1

:found
echo 使用 Python：%PY%
echo 正在生成诊断日志（如需联网安装会一并尝试）...
%PY% 诊断.py > 诊断日志.txt 2>&1
echo.
echo ===== 诊断结果 =====
type 诊断日志.txt
echo.
echo （已保存为 诊断日志.txt）
pause
