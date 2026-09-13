"""Colours, fonts and ttk styling for the whole application."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

BG = "#141619"
SURFACE = "#1b1e23"
SURFACE_ALT = "#20242b"
SURFACE_HOVER = "#262b34"
BORDER = "#2c313a"
BORDER_STRONG = "#3a4150"
TEXT = "#e7e9ec"
TEXT_MUTED = "#98a2b3"
TEXT_DIM = "#6f7885"
ACCENT = "#5b8cff"
ACCENT_HOVER = "#7aa2ff"
ACCENT_DARK = "#3c63c9"
OK = "#3ecf8e"
WARN = "#e2b341"
ERROR = "#e5686a"
BADGE_BG = "#262b34"

FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"
# Preferred families, best CJK coverage first (the UI is bilingual).
FONT_CANDIDATES = ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "TkDefaultFont")
MONO_CANDIDATES = ("Cascadia Mono", "Consolas", "Courier New", "Courier")


class Fonts:
    """Resolved font objects (created after a Tk root exists)."""

    def __init__(self) -> None:
        available = set(tkfont.families())
        family = next((name for name in FONT_CANDIDATES if name in available), "TkDefaultFont")
        mono = next((name for name in MONO_CANDIDATES if name in available), "Courier")
        self.base = tkfont.Font(family=family, size=10)
        self.small = tkfont.Font(family=family, size=9)
        self.bold = tkfont.Font(family=family, size=10, weight="bold")
        self.h1 = tkfont.Font(family=family, size=16, weight="bold")
        self.h2 = tkfont.Font(family=family, size=12, weight="bold")
        self.nav = tkfont.Font(family=family, size=11)
        self.mono = tkfont.Font(family=mono, size=9)


_fonts: Fonts | None = None


def fonts() -> Fonts:
    global _fonts
    if _fonts is None:
        _fonts = Fonts()
    return _fonts


def apply_theme(root: tk.Misc) -> ttk.Style:
    """Configure ttk + classic widget colours and return the style object."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    f = fonts()
    root.option_add("*Font", f.base)

    style.configure(".", background=BG, foreground=TEXT, fieldbackground=SURFACE_ALT,
                    bordercolor=BORDER, focuscolor=ACCENT, font=f.base)
    style.configure("TFrame", background=BG)
    style.configure("Surface.TFrame", background=SURFACE)
    style.configure("Alt.TFrame", background=SURFACE_ALT)
    style.configure("Card.TFrame", background=SURFACE, relief="flat", borderwidth=1)

    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Surface.TLabel", background=SURFACE, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=TEXT_MUTED)
    style.configure("MutedSurface.TLabel", background=SURFACE, foreground=TEXT_MUTED)
    style.configure("H1.TLabel", background=BG, foreground=TEXT, font=f.h1)
    style.configure("H2.TLabel", background=BG, foreground=TEXT, font=f.h2)
    style.configure("Mono.TLabel", background=SURFACE, foreground=TEXT, font=f.mono)
    style.configure("Ok.TLabel", background=BG, foreground=OK)
    style.configure("Warn.TLabel", background=BG, foreground=WARN)
    style.configure("Error.TLabel", background=BG, foreground=ERROR)
    style.configure("Accent.TLabel", background=BG, foreground=ACCENT)

    style.configure("TButton", background=SURFACE_ALT, foreground=TEXT, borderwidth=1,
                    focusthickness=0, padding=(10, 5), relief="flat")
    style.map("TButton",
              background=[("pressed", ACCENT_DARK), ("active", SURFACE_HOVER),
                          ("disabled", SURFACE)],
              foreground=[("disabled", TEXT_DIM)],
              bordercolor=[("focus", ACCENT)])
    style.configure("Accent.TButton", background=ACCENT, foreground="#0d1016",
                    font=f.bold, padding=(12, 6))
    style.map("Accent.TButton",
              background=[("pressed", ACCENT_DARK), ("active", ACCENT_HOVER),
                          ("disabled", "#2b3346")],
              foreground=[("disabled", TEXT_DIM)])
    style.configure("Ghost.TButton", background=SURFACE, foreground=TEXT_MUTED, padding=(8, 4))
    style.map("Ghost.TButton", background=[("active", SURFACE_HOVER)], foreground=[("active", TEXT)])
    style.configure("Nav.TButton", background=SURFACE, foreground=TEXT_MUTED, anchor="w",
                    padding=(14, 10), font=f.nav, borderwidth=0)
    style.map("Nav.TButton", background=[("active", SURFACE_HOVER)], foreground=[("active", TEXT)])
    style.configure("NavActive.TButton", background=SURFACE_HOVER, foreground=TEXT, anchor="w",
                    padding=(14, 10), font=f.nav, borderwidth=0)

    style.configure("TCheckbutton", background=BG, foreground=TEXT, focuscolor=BG)
    style.map("TCheckbutton", background=[("active", BG)], foreground=[("disabled", TEXT_DIM)])
    style.configure("Surface.TCheckbutton", background=SURFACE, foreground=TEXT, focuscolor=SURFACE)
    style.map("Surface.TCheckbutton", background=[("active", SURFACE)])

    style.configure("TEntry", fieldbackground=SURFACE_ALT, foreground=TEXT,
                    insertcolor=TEXT, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    padding=6)
    style.map("TEntry", bordercolor=[("focus", ACCENT)])
    style.configure("TCombobox", fieldbackground=SURFACE_ALT, background=SURFACE_ALT,
                    foreground=TEXT, arrowcolor=TEXT_MUTED, bordercolor=BORDER, padding=4)
    style.map("TCombobox", fieldbackground=[("readonly", SURFACE_ALT)],
              foreground=[("readonly", TEXT)])

    style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT,
                    bordercolor=BORDER, borderwidth=0, rowheight=26)
    style.map("Treeview", background=[("selected", ACCENT_DARK)], foreground=[("selected", "#ffffff")])
    style.configure("Treeview.Heading", background=SURFACE_ALT, foreground=TEXT_MUTED,
                    relief="flat", padding=(8, 6), font=f.small)
    style.map("Treeview.Heading", background=[("active", SURFACE_HOVER)])

    style.configure("TProgressbar", background=ACCENT, troughcolor=SURFACE_ALT,
                    bordercolor=SURFACE_ALT, lightcolor=ACCENT, darkcolor=ACCENT, thickness=6)
    style.configure("Vertical.TScrollbar", background=SURFACE_ALT, troughcolor=BG,
                    bordercolor=BG, arrowcolor=TEXT_MUTED, relief="flat")
    style.map("Vertical.TScrollbar", background=[("active", SURFACE_HOVER)])
    style.configure("Horizontal.TScrollbar", background=SURFACE_ALT, troughcolor=BG,
                    bordercolor=BG, arrowcolor=TEXT_MUTED, relief="flat")

    style.configure("TSeparator", background=BORDER)
    style.configure("TLabelframe", background=BG, foreground=TEXT_MUTED, bordercolor=BORDER)
    style.configure("TLabelframe.Label", background=BG, foreground=TEXT_MUTED, font=f.small)

    for widget_name, options in (
        ("Toplevel", {"background": BG}),
        ("Text", {"background": SURFACE, "foreground": TEXT, "insertbackground": TEXT,
                  "selectbackground": ACCENT_DARK, "relief": "flat", "borderwidth": 0}),
        ("Canvas", {"background": BG, "highlightthickness": 0}),
        ("Listbox", {"background": SURFACE, "foreground": TEXT, "selectbackground": ACCENT_DARK}),
    ):
        try:
            root.option_add(f"*{widget_name}.background", options.get("background", BG))
        except tk.TclError:
            pass
    return style
