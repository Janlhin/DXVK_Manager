"""Measure where the UI spends its time."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DXVK_MANAGER_HOME", str(Path(tempfile.gettempdir()) / "dxvk-toolkit-perf"))

from dxvk_toolkit import installer, steam, confspec  # noqa: E402
from dxvk_toolkit.gui import app as app_module  # noqa: E402
from dxvk_toolkit.util import looks_like_dxvk  # noqa: E402


def t(label, fn, repeat=1):
    start = time.perf_counter()
    result = None
    for _ in range(repeat):
        result = fn()
    elapsed = (time.perf_counter() - start) / repeat
    print(f"{label:<46} {elapsed * 1000:9.1f} ms")
    return result, elapsed


print("=== 后台/数据层 ===")
games = steam.scan_steam_games()
print(f"{'games found':<46} {len(games)}")

def inspect_all():
    return [installer.inspect(g.install_dir) for g in games if g.exists]

t("installer.inspect() x 已安装游戏 (UI 线程调用)", inspect_all)

probe_targets = []
for g in games[:12]:
    if g.exists:
        for dll in ("d3d11.dll", "dxgi.dll", "d3d9.dll"):
            p = g.install_dir / dll
            if p.is_file():
                probe_targets.append(p)
print(f"{'existing D3D dlls in first 12 games':<46} {len(probe_targets)}")
if probe_targets:
    t("looks_like_dxvk() 单次 (读 2MB)", lambda: looks_like_dxvk(probe_targets[0]), repeat=5)

t("installer.inspect() 单款游戏", lambda: installer.inspect(games[0].install_dir), repeat=5)

print("\n=== 界面构建 ===")
cached = {}
def build():
    app = app_module.build_app()
    app.update()
    cached["app"] = app
    return app

app, build_time = t("build_app() 全量构建（启动时）", build)

games_tab = app.tab("games")
config_tab = app.tab("config")
config_tab.on_show()
app.update()

# Feed the games tab the real game list, then time a render.
games_tab.games = games
games_tab.loaded_once = True
t("游戏页 _render() 48 款（含 inspect）", lambda: games_tab._render())
t("游戏页 _render() 再来一次（无缓存优化）", lambda: games_tab._render())

t("配置页 render_options() 基础模式", lambda: config_tab.render_options())
config_tab.advanced_var.set(True)
t("配置页 render_options() 高级模式 87 项", lambda: config_tab.render_options())
t("配置页 搜索过滤一次", lambda: (config_tab.search.set("frame"), config_tab.render_options()))
t("配置页 current_text()", lambda: config_tab.current_text())

t("切换页面 games->config->games", lambda: (app.show_tab("config"), app.show_tab("games")), repeat=3)

app.runner.stop()
app.destroy()
