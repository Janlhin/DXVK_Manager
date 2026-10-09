"""Compare the config layer against the captured golden output.

Byte equality here is the proof that restructuring the config modules (the
confkit extraction) changed nothing that users can see.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DXVK_MANAGER_HOME", str(Path(tempfile.gettempdir()) / "dxvk-golden"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capture_golden import CASES, normalize  # noqa: E402

from dxvk_toolkit import confbuild, confspec  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden"


def main() -> int:
    problems: list[str] = []
    checks: list[str] = []

    model = confspec.load_model()

    # --- catalogue ------------------------------------------------------
    expected = json.loads((GOLDEN / "catalogue.json").read_text(encoding="utf-8"))
    actual = [
        {
            "key": group.key,
            "label": group.label,
            "type": group.type,
            "tier": confspec.tier_of(group.key, group.members[0].section if group.members else ""),
            "sections": [member.section for member in group.members],
            "qualified": [member.qualified for member in group.members],
            "summary": group.summary(120),
            "example": group.example,
        }
        for group in model.groups
    ]
    if len(actual) != len(expected):
        problems.append(f"catalogue size {len(actual)} != {len(expected)}")
    else:
        for got, want in zip(actual, expected):
            for field in want:
                if got.get(field) != want.get(field):
                    problems.append(
                        f"{want['key']}.{field}: {str(got.get(field))[:50]!r} != {str(want.get(field))[:50]!r}"
                    )
                    break
        checks.append(f"catalogue matches ({len(actual)} options)")

    # --- generated files -------------------------------------------------
    # conf_*  = documentation comments included (the default)
    # plain_* = comments off; these files date from before the comment feature,
    #           so they also prove the confkit extraction changed nothing.
    for prefix, comments in (("conf", True), ("plain", False)):
        for name, values in CASES.items():
            want = normalize((GOLDEN / f"{prefix}_{name}.txt").read_text(encoding="utf-8"))
            got = normalize(confbuild.build_conf(model.groups, values,
                                                 section_order=model.section_order,
                                                 comments=comments))
            if got == want:
                checks.append(f"{prefix}_{name} identical")
            else:
                problems.append(f"{prefix}_{name} differs")
                for i, (a, b) in enumerate(zip(got.splitlines(), want.splitlines())):
                    if a != b:
                        problems.append(f"  first diff line {i + 1}: {a!r} != {b!r}")
                        break

    # --- the comment feature itself --------------------------------------
    sample = confbuild.build_conf(model.groups, {"maxFrameRate": 60},
                                  section_order=model.section_order)
    if "# 帧率上限" in sample:
        checks.append("comments carry the Chinese documentation")
    else:
        problems.append("comments missing from the generated file")
    if all(len(line) <= 76 or not line.startswith("#") for line in sample.splitlines()):
        checks.append("comment lines stay within 76 display columns")
    else:
        problems.append("a comment line is wider than 76 columns")

    for line in checks:
        print(f"  [OK  ] {line}")
    for line in problems[:12]:
        print(f"  [FAIL] {line}")
    print(f"result: {'PASS' if not problems else 'FAIL'} ({len(problems)} problems)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
