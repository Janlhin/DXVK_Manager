r"""Command line entry point: launches the GUI or runs a single operation.

Examples
--------
    python -m dxvk_toolkit                      # start the window
    python -m dxvk_toolkit --scan-games         # list detected games
    python -m dxvk_toolkit --versions           # list downloadable versions
    python -m dxvk_toolkit --download v2.7.1    # fetch one version into the cache
    python -m dxvk_toolkit --install v2.7.1 --game "D:\Games\Foo"
    python -m dxvk_toolkit --restore --game "D:\Games\Foo"
    python -m dxvk_toolkit --gen-conf --set hud=fps --set maxFrameRate=60 -o dxvk.conf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import confbuild, confspec, installer, sources, steam
from .util import human_size, setup_logging


def _parse_set(values: list[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in values or []:
        if "=" not in item:
            raise SystemExit(f"--set expects key=value, got: {item}")
        key, _, value = item.partition("=")
        result[key.strip()] = value
    return result


def cmd_scan_games(_args: argparse.Namespace) -> int:
    games = steam.scan_steam_games()
    print(f"Steam root: {steam.steam_root()}")
    print(f"Libraries : {', '.join(str(p) for p in steam.library_folders())}")
    print(f"Games     : {len(games)}")
    for game in games:
        if not game.exists:
            continue
        info = steam.describe_game(game.install_dir)
        status = installer.inspect(game.install_dir)
        state = f"{status.kind} {status.version}" if status.patched else "clean"
        print(
            f"  {game.appid:>8}  {game.name[:40]:<42} {info['direct3d']:<16} "
            f"{info['arch'] or '-':<5} {state}"
        )
    return 0


def cmd_versions(args: argparse.Namespace) -> int:
    releases = (
        sources.fetch_dxvk_releases() if args.kind == "dxvk" else sources.fetch_gplasync_releases()
    )
    for release in releases[: args.limit or len(releases)]:
        mark = "*" if sources.is_installed(release.kind, release.version) else " "
        print(f" {mark} {release.version:<14} {release.date or '-':<12} {human_size(release.size)}")
    print(f"total: {len(releases)}")
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    releases = (
        sources.fetch_dxvk_releases() if args.kind == "dxvk" else sources.fetch_gplasync_releases()
    )
    match = next((r for r in releases if r.version == args.download), None)
    if match is None:
        match = next(
            (r for r in releases if r.version.lstrip("v") == args.download.lstrip("v")), None
        )
    if match is None:
        print(f"version not found: {args.download}", file=sys.stderr)
        return 1

    def progress(done: int, total: int) -> None:
        percent = f"{done * 100 / total:.0f}%" if total else human_size(done)
        print(f"\r  downloading {percent}", end="", flush=True)

    path = sources.download_release(match, progress=progress)
    print(f"\n  extracted to {path}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    game_dir = Path(args.game).expanduser()
    result = installer.install(
        game_dir,
        args.kind,
        args.download,
        arch=args.arch or "",
        d3d_hint=args.d3d or steam.guess_direct3d(game_dir),
        force_backup=args.force_backup,
    )
    print(result.message)
    if result.warning:
        print(f"warning: {result.warning}")
    return 0 if result.success else 1


def cmd_restore(args: argparse.Namespace) -> int:
    result = installer.restore(Path(args.game).expanduser())
    print(result.message)
    return 0 if result.success else 1


def cmd_status(args: argparse.Namespace) -> int:
    for raw in args.game or []:
        game_dir = Path(raw).expanduser()
        status = installer.inspect(game_dir)
        print(f"{game_dir}")
        print(f"  patched : {status.patched} {status.kind} {status.version}".rstrip())
        print(f"  backups : {', '.join(status.backup_files) or '-'}")
        print(f"  dxvk    : {', '.join(status.dxvk_files) or '-'}")
        print(f"  conf    : {status.conf_present}")
    return 0


def cmd_gen_conf(args: argparse.Namespace) -> int:
    model = confspec.load_model(Path(args.reference) if args.reference else None)
    if model.option_count == 0:
        print("no reference file found; pass --reference path/to/dxvk.conf", file=sys.stderr)
        return 1
    values = _parse_set(args.set)
    unknown = [key for key in values if key not in {g.key for g in model.groups}]
    if unknown:
        print(f"warning: unknown option(s): {', '.join(unknown)}", file=sys.stderr)
    text = confbuild.build_conf(model.groups, values, section_order=model.section_order)
    if args.output:
        target = Path(args.output).expanduser()
        target.write_text(text, encoding="utf-8", newline="\r\n")
        print(f"wrote {target} ({confbuild.count_lines(text)} option lines)")
    else:
        print(text, end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dxvk_toolkit", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose logging")
    parser.add_argument("--no-gui", action="store_true", help="never start the window")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--scan-games", action="store_true", help="list detected games")
    group.add_argument("--versions", action="store_true", help="list downloadable versions")
    group.add_argument("--download", metavar="VERSION", help="download a version")
    group.add_argument("--install", dest="download", metavar="VERSION",
                       help="install a cached version into --game")
    group.add_argument("--restore", action="store_true", help="restore backups in --game")
    group.add_argument("--status", action="store_true", help="show the state of --game folders")
    group.add_argument("--gen-conf", action="store_true", help="generate a dxvk.conf")

    parser.add_argument("--kind", choices=("dxvk", "gplasync"), default="dxvk")
    parser.add_argument("--game", action="append", help="game folder (repeatable)")
    parser.add_argument("--arch", choices=("x32", "x64"), default="")
    parser.add_argument("--d3d", default="")
    parser.add_argument("--force-backup", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="limit --versions output")
    parser.add_argument("--reference", help="dxvk.conf used by --gen-conf")
    parser.add_argument("--set", action="append", metavar="KEY=VALUE",
                        help="option for --gen-conf (repeatable)")
    parser.add_argument("-o", "--output", help="output file for --gen-conf")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    if args.scan_games:
        return cmd_scan_games(args)
    if args.versions:
        return cmd_versions(args)
    if args.download and args.install is None and args.game:
        return cmd_install(args)
    if args.download:
        return cmd_download(args)
    if args.restore:
        if not args.game:
            parser.error("--restore needs --game")
        return cmd_restore(args)
    if args.status:
        if not args.game:
            parser.error("--status needs --game")
        return cmd_status(args)
    if args.gen_conf:
        return cmd_gen_conf(args)

    from .ui.app_qml import run as run_qml

    return run_qml()


if __name__ == "__main__":
    raise SystemExit(main())
