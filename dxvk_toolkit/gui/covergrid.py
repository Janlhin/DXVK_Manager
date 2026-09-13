"""A responsive, lazily illustrated grid of game cards.

Layout follows what launcher front ends do: portrait cover art, a wrapped
title and a badge row. Only the cards inside the viewport exist as widgets,
and cover art is fetched for those alone, so a library of a few hundred games
stays responsive.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Sequence

from .. import covers
from ..util import log
from . import theme
from .widgets import ScrollFrame

CARD_W, CARD_H = covers.CARD_SIZE
TEXT_H = 48
CARD_TOTAL_H = CARD_H + TEXT_H
GAP = 14
PAD = 16


class CardSpec:
    """Everything one card needs to draw itself."""

    __slots__ = ("key", "title", "platform", "platform_label", "subtitle",
                 "status", "status_kind", "urls", "tooltip")

    def __init__(
        self,
        key: str,
        title: str,
        *,
        platform: str = "manual",
        platform_label: str = "",
        subtitle: str = "",
        status: str = "",
        status_kind: str = "muted",
        urls: Sequence[str] = (),
        tooltip: str = "",
    ) -> None:
        self.key = key
        self.title = title
        self.platform = platform
        self.platform_label = platform_label or platform.title()
        self.subtitle = subtitle
        self.status = status
        self.status_kind = status_kind
        self.urls = list(urls)
        self.tooltip = tooltip


class _Card:
    """One pooled card canvas."""

    __slots__ = ("canvas", "image_id", "title_id", "initial_id", "platform_id",
                 "status_id", "subtitle_id", "outline_id", "spec", "has_photo")

    def __init__(self, parent: tk.Misc) -> None:
        self.canvas = tk.Canvas(
            parent,
            width=CARD_W,
            height=CARD_TOTAL_H,
            background=theme.SURFACE,
            highlightthickness=0,
            bd=0,
        )
        self.outline_id = self.canvas.create_rectangle(
            0, 0, CARD_W - 1, CARD_TOTAL_H - 1, outline=theme.SURFACE, width=2
        )
        self.image_id = self.canvas.create_image(0, 0, anchor="nw")
        self.initial_id = self.canvas.create_text(
            CARD_W / 2, CARD_H / 2, text="", fill="#e7e9ec", font=theme.fonts().h1
        )
        self.title_id = self.canvas.create_text(
            8, CARD_H + 6, text="", anchor="nw", width=CARD_W - 16,
            fill=theme.TEXT, font=theme.fonts().small,
        )
        self.subtitle_id = self.canvas.create_text(
            8, CARD_H + 24, text="", anchor="nw", width=CARD_W - 100,
            fill=theme.TEXT_DIM, font=theme.fonts().small,
        )
        self.platform_id = self.canvas.create_text(
            8, CARD_TOTAL_H - 9, text="", anchor="w",
            fill=theme.TEXT_MUTED, font=theme.fonts().small,
        )
        self.status_id = self.canvas.create_text(
            CARD_W - 8, CARD_TOTAL_H - 9, text="", anchor="e",
            fill=theme.TEXT_MUTED, font=theme.fonts().small,
        )
        self.spec: CardSpec | None = None
        self.has_photo = False


class CoverGrid(ScrollFrame):
    """Scrollable grid of game cards."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        loader: covers.CoverLoader,
        on_select: Callable[[str], None] | None = None,
        on_activate: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(master, background=theme.BG)
        self.loader = loader
        self.on_select = on_select
        self.on_activate = on_activate
        self.specs: list[CardSpec] = []
        self._cards: list[_Card] = []
        self._bound: dict[int, str] = {}  # card index -> game key
        self._visible_range = (0, -1)
        self._columns = 1
        self._selected = ""
        self._last_width = 0

        self.canvas.configure(yscrollincrement=24)
        self.canvas.bind("<Configure>", self._on_resize, add="+")
        self._last_scroll = -1.0
        self._poll_timer: str | None = None
        self._poll_scroll()

    # -- data ------------------------------------------------------------
    def set_specs(self, specs: Sequence[CardSpec]) -> None:
        self.specs = list(specs)
        self._bound.clear()
        for card in self._cards:
            card.canvas.place_forget()
        self._relayout(force=True)

    def update_spec(self, key: str, **fields: Any) -> None:
        for index, spec in enumerate(self.specs):
            if spec.key == key:
                for name, value in fields.items():
                    if hasattr(spec, name):
                        setattr(spec, name, value)
                self._bind_card(index, self._card_for(index), force=True)
                return

    def select(self, key: str) -> None:
        self._selected = key
        for index, card in enumerate(self._cards):
            if card.canvas.winfo_ismapped():
                self._apply_outline(card)

    @property
    def selected(self) -> str:
        return self._selected

    def clear(self) -> None:
        self.set_specs([])

    # -- layout ----------------------------------------------------------
    def _on_resize(self, _event: tk.Event) -> None:
        self._relayout()

    def _poll_scroll(self) -> None:
        """Watch the scroll offset so visible cards follow any scroll source."""
        self._poll_timer = None
        try:
            offset = float(self.canvas.canvasy(0))
            if offset != self._last_scroll:
                self._last_scroll = offset
                self._refresh_visible()
            self._poll_timer = self.after(140, self._poll_scroll)
        except tk.TclError:
            self._poll_timer = None

    def destroy(self) -> None:  # noqa: D102 - stop polling when the view goes away
        if self._poll_timer is not None:
            try:
                self.after_cancel(self._poll_timer)
            except tk.TclError:
                pass
            self._poll_timer = None
        super().destroy()

    def _relayout(self, *, force: bool = False) -> None:
        width = self.canvas.winfo_width()
        if width <= 1:
            self.after(60, lambda: self._relayout(force=force))
            return
        columns = max(1, (width - PAD * 2 + GAP) // (CARD_W + GAP))
        if not force and columns == self._columns and width == self._last_width:
            self._refresh_visible()
            return
        self._columns = columns
        self._last_width = width

        rows = (len(self.specs) + columns - 1) // columns if self.specs else 0
        content_height = PAD * 2 + rows * CARD_TOTAL_H + max(0, rows - 1) * GAP
        self.begin_bulk()
        self.inner.configure(height=max(content_height, 1))
        now = set()
        for index in range(len(self.specs)):
            row, column = divmod(index, columns)
            x = PAD + column * (CARD_W + GAP)
            y = PAD + row * (CARD_TOTAL_H + GAP)
            card = self._card_for(index)
            card.canvas.place(x=x, y=y, width=CARD_W, height=CARD_TOTAL_H)
            now.add(index)
        for index, card in enumerate(self._cards):
            if index >= len(self.specs):
                card.canvas.place_forget()
        self.end_bulk()
        self.inner.configure(height=max(content_height, 1))
        self._refresh_visible()

    def _card_for(self, index: int) -> _Card:
        while len(self._cards) <= index:
            card = _Card(self.inner)
            self._cards.append(card)
        return self._cards[index]

    # -- visibility ------------------------------------------------------
    def _refresh_visible(self) -> None:
        if not self.specs:
            self._visible_range = (0, -1)
            return
        height = max(self.canvas.winfo_height(), 1)
        top = self.canvas.canvasy(0)
        bottom = top + height
        row_height = CARD_TOTAL_H + GAP
        first_row = max(0, int((top - PAD) // row_height) - 1)
        last_row = int((bottom - PAD) // row_height) + 1
        first = max(0, first_row * self._columns)
        last = min(len(self.specs) - 1, (last_row + 1) * self._columns - 1)
        if (first, last) == self._visible_range:
            return
        self._visible_range = (first, last)
        for index in range(first, last + 1):
            self._bind_card(index, self._card_for(index))

    def _bind_card(self, index: int, card: _Card, *, force: bool = False) -> None:
        if index >= len(self.specs):
            return
        spec = self.specs[index]
        if not force and self._bound.get(index) == spec.key and card.spec is spec:
            return
        self._bound[index] = spec.key
        card.spec = spec

        photo = covers.photo_for(
            spec.key,
            label=spec.title,
            color=covers.platform_color(spec.platform),
            size=(CARD_W, CARD_H),
        )
        if photo is not None:
            card.canvas.itemconfigure(card.image_id, image=photo)
            card.canvas.coords(card.image_id, 0, 0)
            card.canvas.itemconfigure(card.initial_id, text="")
            card.has_photo = True
            card.canvas.image = photo  # keep the reference alive
        else:
            placeholder = covers.platform_placeholder(spec.platform, (CARD_W, CARD_H))
            if placeholder is not None:
                card.canvas.itemconfigure(card.image_id, image=placeholder)
                card.canvas.coords(card.image_id, 0, 0)
                card.canvas.image = placeholder
                card.has_photo = True
            else:
                card.canvas.itemconfigure(card.image_id, image="")
                card.canvas.create_rectangle(
                    0, 0, CARD_W, CARD_H, fill=covers.platform_color(spec.platform), outline=""
                )
                card.has_photo = False
            initials = "".join(word[0] for word in spec.title.split()[:3]).upper() or "?"
            card.canvas.itemconfigure(card.initial_id, text=initials)
            card.canvas.coords(card.initial_id, CARD_W / 2, CARD_H / 2)

        card.canvas.itemconfigure(card.title_id, text=_shorten(spec.title, 46))
        card.canvas.itemconfigure(card.subtitle_id, text=spec.subtitle or "")
        card.canvas.itemconfigure(card.platform_id, text=spec.platform_label)
        status_color = {
            "ok": theme.OK,
            "warn": theme.WARN,
            "muted": theme.TEXT_DIM,
            "error": theme.ERROR,
        }.get(spec.status_kind, theme.TEXT_DIM)
        card.canvas.itemconfigure(card.status_id, text=spec.status or "", fill=status_color)
        card.canvas.itemconfigure(card.platform_id, fill=theme.TEXT_MUTED)
        self._apply_outline(card)

        if not card.canvas.bind("<Button-1>"):
            card.canvas.bind("<Button-1>", lambda _e, c=card: self._click(c))
            card.canvas.bind("<Double-1>", lambda _e, c=card: self._activate(c))
            card.canvas.bind("<Enter>", lambda _e, c=card: self._hover(c, True))
            card.canvas.bind("<Leave>", lambda _e, c=card: self._hover(c, False))

        if not covers.card_path(spec.key).is_file() and spec.urls:
            self.loader.request(spec.key, spec.urls, self._on_cover)

    def _apply_outline(self, card: _Card) -> None:
        spec = card.spec
        if spec is None:
            return
        if spec.key == self._selected:
            card.canvas.itemconfigure(card.outline_id, outline=theme.ACCENT)
        else:
            card.canvas.itemconfigure(card.outline_id, outline=theme.SURFACE)

    # -- interaction -----------------------------------------------------
    def _click(self, card: _Card) -> None:
        if card.spec is None:
            return
        self._selected = card.spec.key
        for other in self._cards:
            self._apply_outline(other)
        if self.on_select:
            self.on_select(card.spec.key)

    def _activate(self, card: _Card) -> None:
        if card.spec is not None and self.on_activate:
            self.on_activate(card.spec.key)

    def _hover(self, card: _Card, entering: bool) -> None:
        if card.spec is None:
            return
        if entering:
            card.canvas.configure(background=theme.SURFACE_ALT)
            if card.spec.key != self._selected:
                card.canvas.itemconfigure(card.outline_id, outline=theme.BORDER_STRONG)
        else:
            card.canvas.configure(background=theme.SURFACE)
            self._apply_outline(card)

    # -- covers ----------------------------------------------------------
    def _on_cover(self, key: str, ok: bool) -> None:
        if not ok:
            return
        covers.forget(key)
        for index, card in enumerate(self._cards):
            spec = card.spec
            if spec is not None and spec.key == key and card.canvas.winfo_ismapped():
                self._bind_card(index, card, force=True)


def _shorten(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
