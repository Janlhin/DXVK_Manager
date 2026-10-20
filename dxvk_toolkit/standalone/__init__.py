"""The standalone dxvk.conf configurator.

The full application is a DXVK version manager: it scans games, downloads
releases and installs DLLs. The configuration editor is a separate concern -
given a dxvk.conf it produces a customised one - and it is useful on its own
for people who only want the generator.

This package assembles that tool from the parts that already exist:

* :mod:`dxvk_toolkit.confkit` - the pure configuration core (parsing, the
  option catalogue, generation). Standard library only.
* :mod:`dxvk_toolkit.ui.conf_model` - the option catalogue as a Qt model.
* The QML components of the configuration page - reused verbatim, so the two
  tools cannot drift apart visually.

What is *not* reused is the bridge: the full app's bridge exposes 56 slots
about games, versions and installation, none of which exist here. This one
exposes only what the configurator does, and its concept of a "target" is a
.conf file rather than a game folder.
"""

from __future__ import annotations

__all__ = ["main"]


def main() -> int:
    """Entry point of the standalone configurator."""
    from .app import run

    return run()
