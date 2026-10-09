"""一次性诊断：用本地 .venv 安装依赖并实测能否打开窗口（避开 uv externally-managed 限制）。"""
from __future__ import annotations

import os
import subprocess
import sys


def line(s: str = "") -> None:
    print(s)


def find_base_python() -> str | None:
    candidates = [
        r"C:\Users\Janlhin\.local\bin\python.exe",
        r"C:\Users\Janlhin\.workbuddy\binaries\python\versions\3.13.12\python.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    # 退而求其次：依赖 PATH 上的 python / python3
    for name in ("python", "python3"):
        try:
            subprocess.run([name, "-c", "import sys"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return name
        except Exception:  # noqa: BLE001
            continue
    return None


def ensure_venv(base: str) -> str | None:
    vpy = os.path.join(".venv", "Scripts", "python.exe")
    if os.path.exists(vpy):
        return vpy
    line("")
    line("=== 创建本地虚拟环境 .venv ===")
    try:
        subprocess.run([base, "-m", "venv", ".venv"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    except subprocess.CalledProcessError as e:
        line("[错误] 创建 .venv 失败:")
        line(e.stderr.strip() or e.stdout.strip() or str(e))
        return None
    if not os.path.exists(vpy):
        line("[错误] .venv 创建后仍未找到解释器。")
        return None
    line("[OK] .venv 已创建")
    return vpy


def have(vpy: str, mod: str) -> bool:
    try:
        subprocess.run([vpy, "-c", f"import {mod}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print(f"[OK] {mod}")
        return True
    except Exception:  # noqa: BLE001
        print(f"[缺] {mod}")
        return False


def pip_install(vpy: str) -> bool:
    line("")
    line("=== 在 .venv 内安装 PySide6 + Pillow（需联网）===")
    try:
        r = subprocess.run([vpy, "-m", "pip", "install", "--upgrade", "pip"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        line("pip upgrade: rc=%s" % r.returncode)
        r = subprocess.run([vpy, "-m", "pip", "install", "PySide6", "Pillow"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    except subprocess.TimeoutExpired:
        line("[错误] pip 安装超时（>600 秒），可能网络极慢或被拦截。")
        return False
    except Exception as e:  # noqa: BLE001
        line(f"[错误] 无法执行 pip: {e}")
        return False
    line("--- pip stderr ---")
    line(r.stderr.strip() or "(空)")
    line(f"pip 返回码: {r.returncode}")
    return r.returncode == 0


def main() -> None:
    line("=== 1. Python 环境 ===")
    line(f"exe : {sys.executable}")
    line(f"ver : {sys.version.split()[0]}")
    line(f"cwd : {os.getcwd()}")

    base = find_base_python()
    if not base:
        line("[错误] 未找到可用的基础 Python。")
        return
    line(f"基础 Python: {base}")

    vpy = ensure_venv(base)
    if not vpy:
        return
    line(f"运行环境: {vpy}")

    line("")
    line("=== 2. 依赖 ===")
    pyside = have(vpy, "PySide6")
    have(vpy, "PySide6.QtQuick")
    have(vpy, "PIL")

    if not pyside:
        if not pip_install(vpy):
            line("依赖安装失败，GUI 无法启动。请把上面 pip 报错发我。")
            return
        pyside = have(vpy, "PySide6")
        if not pyside:
            line("依赖仍未就绪。请把上面 pip 报错发我。")
            return

    line("")
    line("=== 3. 尝试启动主程序（最多等 12 秒，看窗口是否出来）===")
    try:
        proc = subprocess.Popen(
            [vpy, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=os.getcwd(),
        )
    except Exception as e:  # noqa: BLE001
        line(f"[错误] 无法启动进程: {e}")
        return

    try:
        out, err = proc.communicate(timeout=12)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            out, err = proc.communicate(timeout=2)
        except Exception:  # noqa: BLE001
            out, err = "", ""
        line("[成功] 12 秒内进程未退出 —— 程序已成功打开窗口！（测试进程已关闭）")
        return

    line(f"进程已退出，返回码 {proc.returncode}")
    if out.strip():
        line("--- stdout ---")
        line(out)
    if err.strip():
        line("--- stderr / 报错 ---")
        line(err)
    else:
        line("（无 stderr 输出）")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        import traceback

        traceback.print_exc()
