"""Coverage for the pure-stdlib core: build / model / parse round trip.

These tests need no Qt, no network, no asset files, so they run under the
sole `verify` gate on any machine (incl. CI). Kept in their own file so the
growth of core coverage is visible.
"""

import sys

sys.path.insert(0, ".")

from dxvk_toolkit.confkit.build import (
    build_conf,
    count_lines,
    format_value,
    selection_summary,
    wrap_comment,
)
from dxvk_toolkit.confkit.model import Member, OptionGroup
from dxvk_toolkit.confkit.parse import build_model


def _group(key, sections, example, type_, comment=""):
    members = [Member(section=s, key=key, example=example, type=type_, comment=comment)
              for s in sections]
    return OptionGroup(key=key, members=members, type=type_, example=example, comment=comment)


# --- format_value: the quoting rules DXVK relies on -------------------------
def test_format_value_none_and_empty():
    assert format_value(None, "string") is None
    assert format_value("", "string") is None
    assert format_value("   ", "string") is None


def test_format_value_boolean():
    assert format_value(True, "boolean") == "True"
    assert format_value(False, "boolean") is None
    assert format_value("true", "boolean") == "True"
    assert format_value("no", "boolean") is None


def test_format_value_number_passthrough():
    assert format_value(60, "number") == "60"
    # a DXVK "version" like 12_1 is not numeric, so it is quoted...
    assert format_value("12_1", "number") == '"12_1"'
    # ...and only stays bare when the option opts in to bare writing
    assert format_value("12_1", "string", bare=True) == "12_1"


def test_format_value_quoting():
    # normal word, no bare request -> quoted
    assert format_value("fps", "string") == '"fps"'
    # a value containing '#' must be quoted (would break the line otherwise)
    assert format_value("a#b", "string") == '"a#b"'
    # an embedded quote is escaped
    assert format_value('he"llo', "string") == '"he\\"llo"'


def test_format_value_bare_opt_in():
    # enum-style values stay bare when the option prefers it
    assert format_value("Auto", "string", bare=True) == "Auto"
    # but a value with a space is still quoted even when bare is requested
    assert format_value("two words", "string", bare=True) == '"two words"'


# --- build_conf: selection -> dxvk.conf text --------------------------------
def test_build_conf_writes_every_section():
    g = _group("hud", ["dxvk", "d3d11"], '"fps"', "string")
    text = build_conf([g], {"hud": "fps"}, comments=False)
    assert "dxvk.hud = \"fps\"" in text
    assert "d3d11.hud = \"fps\"" in text
    assert "# [dxvk]" in text and "# [d3d11]" in text


def test_build_conf_skips_unset():
    g = _group("hud", ["dxvk"], '"fps"', "string")
    text = build_conf([g], {"hud": None}, comments=False)
    assert "No options selected" in text
    assert "dxvk.hud" not in text


def test_build_conf_respects_section_order():
    g1 = _group("hud", ["dxvk"], '"fps"', "string")
    g2 = _group("maxFrameRate", ["dxgi"], "60", "number")
    text = build_conf([g1, g2], {"hud": "fps", "maxFrameRate": 60},
                      comments=False, section_order=["dxgi", "dxvk"])
    assert text.index("# [dxgi]") < text.index("# [dxvk]")


# --- count_lines / selection_summary ----------------------------------------
def test_count_lines_ignores_comments_and_blanks():
    text = "# a comment\n\ndxvk.hud = \"fps\"\n\n# another\n"
    assert count_lines(text) == 1


def test_selection_summary_empty_and_count():
    assert selection_summary({}) == "no options selected"
    assert selection_summary({"hud": "fps", "maxFrameRate": 60}) == "2 option(s) selected"
    # an empty value is not "active"
    assert selection_summary({"hud": ""}) == "no options selected"


# --- wrap_comment: monospace-width wrapping, CJK breaks per char ------------
def test_wrap_comment_latin_token_integrity():
    lines = wrap_comment("hello world this is a fairly long sentence to wrap", width=24)
    for line in lines:
        assert len(line) <= 24  # latin chars are single width -> char count == column count
    joined = " ".join(l[2:] if l.startswith("# ") else l for l in lines)
    assert "hello" in joined and "sentence" in joined


def test_wrap_comment_cjk_double_width():
    from dxvk_toolkit.confkit.build import display_width
    text = "这是一段用来测试中文换行宽度是否正确的较长文字内容示例"
    lines = wrap_comment(text, width=12)
    for line in lines:
        # strip the "# " prefix before measuring
        body = line[2:] if line.startswith("# ") else line
        assert display_width(body) <= 12
    flat = "".join(l[2:] if l.startswith("# ") else l for l in lines)
    assert "中文换行" in flat


# --- Member / OptionGroup derived properties --------------------------------
def test_member_example_flags():
    q = Member(section="dxvk", key="hud", example='"fps"', type="string", comment="")
    assert q.quoted_example is True
    assert q.bare_example is False
    b = Member(section="dxvk", key="vendor", example="Auto", type="string", comment="")
    assert b.quoted_example is False
    assert b.bare_example is True
    n = Member(section="dxvk", key="rate", example="60", type="number", comment="")
    assert n.bare_example is False


def test_option_group_prefers_bare_and_default():
    bare_g = _group("vendor", ["dxvk"], "Auto", "string")
    assert bare_g.prefers_bare is True
    bool_g = _group("async", ["dxvk"], "False", "boolean")
    assert bool_g.prefers_bare is False
    assert bool_g.default_value() is False
    num_g = _group("maxFrameRate", ["dxgi"], "60", "number")
    assert num_g.default_value() == "60"
    str_g = _group("hud", ["dxvk"], '"fps"', "string")
    assert str_g.default_value() == ""


# --- build_model: parsing a realistic reference produces a usable catalogue -
def test_build_model_roundtrip():
    text = (
        "[dxvk]\n"
        "dxvk.hud = \"fps\"\n"
        "dxvk.maxFrameRate = 60\n"
        "\n"
        "[dxgi]\n"
        "dxgi.maxFrameRate = 60\n"
    )
    model = build_model(text, source="unit-test")
    by_key = {g.key: g for g in model.groups}
    assert "hud" in by_key and "maxFrameRate" in by_key
    # the same option across two sections collapses into one group
    assert set(by_key["maxFrameRate"].sections) == {"dxvk", "dxgi"}
    assert model.option_count >= 2
    # section order is preserved
    assert model.section_order[:2] == ["dxvk", "dxgi"]


if __name__ == "__main__":
    # Standalone runner: lets us verify without pytest installed (sandbox-safe).
    import traceback

    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in funcs:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception:
            failed += 1
            print("FAIL", fn.__name__)
            traceback.print_exc()
    print(f"\nRESULT: {len(funcs) - failed}/{len(funcs)} passed")
    sys.exit(1 if failed else 0)
