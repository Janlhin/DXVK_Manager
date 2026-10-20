"""Static checks over the QML sources.

The QML side has no unit test suite: a wrong property name or a broken
relative import only shows up as a silent runtime warning, and the page
still "renders" off screen. This module closes the gap without needing a
GUI: it parses the QML text and checks the mistakes that a refactor of the
QML tree actually makes.

Three families of checks:

1. Imports - every ``import`` of a relative path must resolve to a real
   file. Moving a QML file into a sub-directory breaks ``import
   "theme.js"`` silently (the theme becomes undefined and every colour
   renders black), so this is checked mechanically.
2. Ids - ids must be unique inside a file. Two objects with the same id
   in one document make the reference ambiguous, and a split that copies a
   block tends to introduce exactly that.
3. Inventory - the set of ``qsTr`` source strings and the set of
   ``objectName`` values is compared against a recorded baseline. Splitting
   a page into components must not add, drop or translate any user-facing
   string: the English catalogue is compiled from these strings, so a
   silent drop would leave an untranslated label in the English build.
4. Translation contexts - Qt derives the context of a QML ``qsTr()`` from
   the *file name* of the QML file. Every ``qsTr`` string must therefore
   exist in ``assets/i18n/app_en.ts`` under a context named after its own
   file. Splitting ``ConfigPage.qml`` into components silently renamed the
   context and left half the page Chinese in the English build; this check
   makes that class of regression impossible to miss.

Run standalone::

    python tests/qml_check.py

It exits non-zero when a check fails, so it can be wired into the verify
gate. After an intentional wording change, refresh the baseline with::

    python tests/qml_check.py --update-baseline
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QML_DIR = ROOT / "dxvk_toolkit" / "ui" / "qml"
BASELINE = Path(__file__).resolve().parent / "qml_baseline.json"
TS_CATALOGUE = ROOT / "assets" / "i18n" / "app_en.ts"

# ``import "theme.js" as Th`` / ``import "../theme.js" as Th``
IMPORT_RE = re.compile(r'^\s*import\s+"([^"]+)"', re.MULTILINE)
# ``id: someName`` at the start of a property line
ID_RE = re.compile(r'^\s*id:\s*([A-Za-z_][A-Za-z0-9_]*)\s*$', re.MULTILINE)
# ``objectName: "someName"``
OBJECT_NAME_RE = re.compile(r'objectName:\s*"([^"]+)"')
# ``qsTr("...")`` - the source string is the translation key.
QSTR_ANY_RE = re.compile(r'qsTr\(\s*"((?:[^"\\]|\\.)*)"')


def collect_qml_files() -> list[Path]:
    return sorted(QML_DIR.rglob("*.qml"))


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def check_imports(files: list[Path]) -> list[str]:
    """Relative imports must resolve. This is the top split hazard."""
    problems: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for target in IMPORT_RE.findall(text):
            if not target.endswith((".js", ".qml")):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.is_file():
                problems.append(
                    f'{_rel(path)}: import "{target}" does not resolve '
                    f"(expected {resolved})"
                )
    return problems


def check_ids(files: list[Path]) -> list[str]:
    """Ids must be unique inside a file."""
    problems: list[str] = []
    for path in files:
        ids = ID_RE.findall(path.read_text(encoding="utf-8"))
        seen: set[str] = set()
        for name in ids:
            if name in seen:
                problems.append(f"{_rel(path)}: duplicate id '{name}'")
            seen.add(name)
    return problems


def _unescape(raw: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and i + 1 < len(raw):
            out.append({"n": "\n", "t": "\t", "r": "\r", '"': '"',
                        "\\": "\\", "'": "'"}.get(raw[i + 1], raw[i + 1]))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def load_catalogue() -> dict[str, dict[str, str]]:
    """context -> {source: translation} from assets/i18n/app_en.ts."""
    catalogue: dict[str, dict[str, str]] = {}
    if not TS_CATALOGUE.is_file():
        return catalogue
    root = ET.parse(TS_CATALOGUE).getroot()
    for ctx in root.iter("context"):
        name_el = ctx.find("name")
        if name_el is None or not name_el.text:
            continue
        bucket: dict[str, str] = {}
        for msg in ctx.findall("message"):
            src = msg.find("source")
            tr = msg.find("translation")
            if src is None or src.text is None:
                continue
            bucket[src.text] = (tr.text or "") if tr is not None else ""
        catalogue[name_el.text] = bucket
    return catalogue


def check_translation_contexts(files: list[Path]) -> list[str]:
    """Every qsTr() must be translated under the context of its own QML file.

    Qt uses the QML file name as the translation context. If the catalogue
    does not carry that context, the English build silently falls back to the
    Chinese source string - the page still renders, just half untranslated.
    """
    problems: list[str] = []
    catalogue = load_catalogue()
    if not catalogue:
        return [f"{_rel(TS_CATALOGUE)} is missing or unreadable"]
    for path in files:
        context = path.stem
        text = path.read_text(encoding="utf-8")
        sources = {_unescape(raw) for raw in QSTR_ANY_RE.findall(text)}
        if not sources:
            continue
        bucket = catalogue.get(context)
        if bucket is None:
            problems.append(
                f"{_rel(path)}: no translation context '{context}' in "
                f"{_rel(TS_CATALOGUE)} (the file was split or renamed)"
            )
            continue
        for source in sorted(sources):
            if source not in bucket:
                problems.append(
                    f"{_rel(path)}: '{source}' is not in context '{context}'"
                )
            elif not bucket[source].strip():
                problems.append(
                    f"{_rel(path)}: '{source}' has an empty translation in "
                    f"context '{context}'"
                )
    return problems


def collect_inventory(files: list[Path]) -> dict[str, list[str]]:
    """User-facing strings and object names, the things a split must not change."""
    strings: set[str] = set()
    object_names: set[str] = set()
    for path in files:
        text = path.read_text(encoding="utf-8")
        strings.update(QSTR_ANY_RE.findall(text))
        object_names.update(OBJECT_NAME_RE.findall(text))
    return {
        "qstr": sorted(strings),
        "object_names": sorted(object_names),
    }


def load_baseline() -> dict[str, list[str]]:
    if not BASELINE.is_file():
        return {}
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    return {k: list(v) for k, v in data.items()}


def save_baseline(data: dict[str, list[str]]) -> None:
    BASELINE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    files = collect_qml_files()
    failures: list[str] = []

    failures.extend(check_imports(files))
    failures.extend(check_ids(files))
    failures.extend(check_translation_contexts(files))

    inventory = collect_inventory(files)
    baseline = load_baseline()
    if "--update-baseline" in argv:
        save_baseline(inventory)
        print(
            f"baseline updated: {len(inventory['qstr'])} strings, "
            f"{len(inventory['object_names'])} object names"
        )
        return 0

    if not baseline:
        failures.append(
            "no baseline found - run `python tests/qml_check.py --update-baseline`"
        )
    else:
        for key in ("qstr", "object_names"):
            before = set(baseline.get(key, []))
            after = set(inventory[key])
            for item in sorted(before - after):
                failures.append(
                    f"{key}: '{item}' disappeared (the English catalogue would break)"
                )
            for item in sorted(after - before):
                failures.append(
                    f"{key}: '{item}' is new (needs an English translation)"
                )

    if failures:
        print(f"qml check: FAIL ({len(failures)} problems)")
        for item in failures:
            print(f"  - {item}")
        return 2

    print(
        f"qml check: OK ({len(files)} files, "
        f"{len(inventory['qstr'])} translatable strings, "
        f"{len(inventory['object_names'])} object names)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
