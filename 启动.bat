@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DXVK Version Manager (Python)

py -3.13 -c "import sys" >nul 2>nul
if not errorlevel 1 goto run_pylauncher
python -c "import sys" >nul 2>nul
if not errorlevel 1 goto run_python

echo [错误] 没有找到可用的 Python 解释器。
echo        请安装 Python 3.10 或更高版本（https://www.python.org/downloads/），
echo        安装时务必勾选 Add python.exe to PATH。
echo.
pause
exit /b 1

:run_pylauncher
py -3.13 main.py %*
goto done

:run_python
python main.py %*
goto done

:done
if errorlevel 1 (
    echo.
    echo [提示] 程序异常退出。请把上面的错误信息发给我，我来定位。
    pause
)
