"""Reusable Tkinter widgets: scrolling panes, tables, status bar, tooltips."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Iterable, Sequence

from . import theme


class ScrollFrame(ttk.Frame):
    """A vertically scrolling container; put children inside .inner."""

    def __init__(self, master: tk.Misc, *, background: str = theme.BG, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, background=background, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.inner = ttk.Frame(self.canvas, style="TFrame")
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        # While a list is being rebuilt, every pack() fires a Configure event;
        # recomputing the scroll region each time dominates the rebuild cost.
        self._bulk = False

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def begin_bulk(self) -> None:
        """Suspend scroll-region updates while many children change."""
        self._bulk = True

    def end_bulk(self) -> None:
        """Resume updates and recompute the scroll region exactly once."""
        self._bulk = False
        self._sync_scrollregion()

    def _sync_scrollregion(self) -> None:
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            pass

    def _on_inner_configure(self, _event: tk.Event) -> None:
        if self._bulk:
            return
        self._sync_scrollregion()

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self, _event: tk.Event) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _event: tk.Event) -> None:
        self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event: tk.Event) -> None:
        try:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except tk.TclError:
            pass

    def scroll_to_top(self) -> None:
        self.canvas.yview_moveto(0.0)

    def clear(self) -> None:
        for child in self.inner.winfo_children():
            child.destroy()


class TreePanel(ttk.Frame):
    """A ttk.Treeview with scrollbar, column config and a selection helper."""

    def __init__(
        self,
        master: tk.Misc,
        columns: Sequence[tuple[str, str, int, str]],
        *,
        height: int = 12,
        on_double_click: Callable[[str], None] | None = None,
        on_select: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(master, style="Surface.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        keys = [column[0] for column in columns]
        self.tree = ttk.Treeview(self, columns=keys, show="headings", height=height,
                                 selectmode="browse")
        for key, heading, width, anchor in columns:
            self.tree.heading(key, text=heading, anchor=anchor)
            self.tree.column(key, width=width, anchor=anchor, stretch=(key == keys[0]))
        self.tree.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

        self.tree.tag_configure("odd", background=theme.SURFACE)
        self.tree.tag_configure("even", background=theme.SURFACE_ALT)
        self.tree.tag_configure("patched", foreground=theme.OK)
        self.tree.tag_configure("muted", foreground=theme.TEXT_MUTED)
        self.tree.tag_configure("warn", foreground=theme.WARN)

        if on_double_click:
            self.tree.bind("<Double-1>", lambda _e: self._fire(on_double_click))
        if on_select:
            self.tree.bind("<<TreeviewSelect>>", lambda _e: self._fire(on_select))

    def _fire(self, callback: Callable[[str], None]) -> None:
        item = self.selected
        if item:
            callback(item)

    @property
    def selected(self) -> str:
        selection = self.tree.selection()
        return selection[0] if selection else ""

    def selected_values(self) -> tuple[Any, ...]:
        item = self.selected
        return tuple(self.tree.item(item, "values")) if item else ()

    def clear(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def add_row(self, values: Sequence[Any], *, iid: str | None = None,
                tags: Iterable[str] = ()) -> str:
        index = len(self.tree.get_children())
        base = "even" if index % 2 else "odd"
        return self.tree.insert("", "end", iid=iid or None, values=tuple(values),
                                tags=tuple({base, *tags}))


class SearchEntry(ttk.Frame):
    """Entry with a placeholder and a debounced change callback."""

    def __init__(self, master: tk.Misc, *, placeholder: str = "Search",
                 on_change: Callable[[str], None] | None = None, width: int = 28) -> None:
        super().__init__(master, style="TFrame")
        self._placeholder = placeholder
        self._on_change = on_change
        self._after_id: str | None = None
        self.variable = tk.StringVar()

        self.entry = ttk.Entry(self, textvariable=self.variable, width=width)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.variable.trace_add("write", self._changed)
        self._show_placeholder()

        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)
        self.entry.bind("<Escape>", lambda _e: self.set(""))

    def _show_placeholder(self) -> None:
        if not self.variable.get():
            self.entry.configure(foreground=theme.TEXT_DIM)
            self.variable.set(self._placeholder)

    def _focus_in(self, _event: tk.Event) -> None:
        if self.variable.get() == self._placeholder:
            self.variable.set("")
            self.entry.configure(foreground=theme.TEXT)

    def _focus_out(self, _event: tk.Event) -> None:
        if not self.variable.get().strip():
            self.variable.set(self._placeholder)
            self.entry.configure(foreground=theme.TEXT_DIM)

    def _changed(self, *_args: Any) -> None:
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
        self._after_id = self.after(220, self._emit)

    def _emit(self) -> None:
        self._after_id = None
        if self._on_change:
            self._on_change(self.value)

    @property
    def value(self) -> str:
        text = self.variable.get()
        return "" if text == self._placeholder else text.strip()

    def set(self, text: str) -> None:
        self.variable.set(text)
        self.entry.configure(foreground=theme.TEXT if text else theme.TEXT_DIM)


class Tooltip:
    """Hover tooltip used for the long option descriptions."""

    def __init__(self, widget: tk.Misc, text: str = "", *, wraplength: int = 620,
                 delay: int = 380) -> None:
        self.widget = widget
        self.text = text
        self.wraplength = wraplength
        self.delay = delay
        self._after: str | None = None
        self._window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def update_text(self, text: str) -> None:
        self.text = text

    def _schedule(self, _event: tk.Event | None = None) -> None:
        self._cancel()
        if self.text:
            self._after = self.widget.after(self.delay, self._show)

    def _cancel(self) -> None:
        if self._after:
            try:
                self.widget.after_cancel(self._after)
            except tk.TclError:
                pass
            self._after = None

    def _show(self) -> None:
        if self._window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 24
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except tk.TclError:
            return
        window = tk.Toplevel(self.widget)
        window.wm_overrideredirect(True)
        window.wm_geometry(f"+{x}+{y}")
        frame = tk.Frame(window, background=theme.BORDER_STRONG, bd=0)
        frame.pack()
        label = tk.Label(frame, text=self.text, justify="left", background=theme.SURFACE_ALT,
                         foreground=theme.TEXT, wraplength=self.wraplength, padx=10, pady=8,
                         font=theme.fonts().small)
        label.pack()
        self._window = window

    def _hide(self, _event: tk.Event | None = None) -> None:
        self._cancel()
        if self._window is not None:
            self._window.destroy()
            self._window = None


class StatusBar(ttk.Frame):
    """Bottom bar with a message, a progress indicator and a right-hand slot."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, style="Surface.TFrame", padding=(12, 6))
        self.columnconfigure(0, weight=1)
        self.message = ttk.Label(self, text="Ready", style="MutedSurface.TLabel")
        self.message.grid(row=0, column=0, sticky="w")
        self.detail = ttk.Label(self, text="", style="MutedSurface.TLabel")
        self.detail.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.progress = ttk.Progressbar(self, mode="determinate", length=180, maximum=100)
        self.progress.grid(row=0, column=2, sticky="e", padx=(12, 0))
        self.progress.grid_remove()

    def set_status(self, text: str, kind: str = "info") -> None:
        colours = {"info": theme.TEXT_MUTED, "ok": theme.OK, "warn": theme.WARN,
                   "error": theme.ERROR}
        self.message.configure(text=text, foreground=colours.get(kind, theme.TEXT_MUTED))

    def show_progress(self, fraction: float | None, text: str = "") -> None:
        if fraction is None:
            self.progress.grid_remove()
            self.detail.configure(text=text)
            return
        self.progress.grid()
        self.progress.configure(value=max(0.0, min(1.0, fraction)) * 100)
        self.detail.configure(text=text)


class ModalDialog(tk.Toplevel):
    """Base class for modal dialogs: centred, themed, Esc closes."""

    def __init__(self, master: tk.Misc, title: str, *, width: int = 720, height: int = 560,
                 resizable: bool = True) -> None:
        super().__init__(master, background=theme.BG)
        self.title(title)
        self.transient(master)
        self.resizable(resizable, resizable)
        self.geometry(self._centered_geometry(master, width, height))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _e: self.close())
        self.body = ttk.Frame(self, style="TFrame", padding=16)
        self.body.pack(fill="both", expand=True)
        self.result: Any = None

    @staticmethod
    def _centered_geometry(master: tk.Misc, width: int, height: int) -> str:
        try:
            master.update_idletasks()
            x = master.winfo_rootx() + max(0, (master.winfo_width() - width) // 2)
            y = master.winfo_rooty() + max(0, (master.winfo_height() - height) // 3)
        except tk.TclError:
            x, y = 200, 160
        return f"{width}x{height}+{x}+{y}"

    def show(self) -> Any:
        self.grab_set()
        self.wait_window(self)
        return self.result

    def close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def labeled_row(master: tk.Misc, label: str, *, style: str = "TLabel") -> ttk.Frame:
    """Small helper: a frame with a muted label, ready for a widget on the right."""
    frame = ttk.Frame(master, style="TFrame")
    ttk.Label(frame, text=label, style=style, width=16).grid(row=0, column=0, sticky="w")
    frame.columnconfigure(1, weight=1)
    return frame


def readonly_text(master: tk.Misc, *, height: int = 20, mono: bool = True) -> tk.Text:
    text = tk.Text(master, height=height, wrap="none", background=theme.SURFACE,
                   foreground=theme.TEXT, insertbackground=theme.TEXT, relief="flat",
                   padx=10, pady=8, highlightthickness=1, highlightbackground=theme.BORDER,
                   highlightcolor=theme.BORDER_STRONG,
                   font=theme.fonts().mono if mono else theme.fonts().base)
    text.configure(state="disabled")
    return text


def set_readonly_text(widget: tk.Text, content: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", content)
    widget.configure(state="disabled")


def hint_label(master: tk.Misc, text: str, *, style: str = "Muted.TLabel") -> ttk.Label:
    return ttk.Label(master, text=text, style=style, wraplength=760, justify="left")
