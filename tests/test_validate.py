"""Boundary validation for the config layer.

Run with:  python -m pytest tests/test_validate.py -q
Or via the single gate:  python -m pytest tests/ -q
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dxvk_toolkit import confkit
from dxvk_toolkit.confkit.validate import (  # noqa: E402
    MAX_CONF_BYTES,
    MAX_LINE_LENGTH,
    ValidationError,
    validate_conf_text,
    validate_model_counts,
    validate_section_name,
)


def _oversize_text() -> str:
    """Many short lines whose total bytes exceed the size limit."""
    lines = ["x" * 100 for _ in range((MAX_CONF_BYTES // 101) + 2)]
    return "\n".join(lines)


class ValidateTextTests(unittest.TestCase):
    def test_accepts_normal_conf(self) -> None:
        validate_conf_text("[dxvk]\ndxvk.hud = \"fps\"\n")

    def test_rejects_oversize(self) -> None:
        with self.assertRaises(ValidationError):
            validate_conf_text(_oversize_text())

    def test_rejects_long_line(self) -> None:
        with self.assertRaises(ValidationError):
            validate_conf_text("x" * (MAX_LINE_LENGTH + 1))

    def test_rejects_non_str(self) -> None:
        with self.assertRaises(ValidationError):
            validate_conf_text(b"[dxvk]")  # type: ignore[arg-type]


class ValidateSectionTests(unittest.TestCase):
    def test_rejects_empty_section(self) -> None:
        with self.assertRaises(ValidationError):
            validate_section_name("")

    def test_accepts_valid_section(self) -> None:
        validate_section_name("dxvk")
        validate_section_name("d3d11")


class ValidateCountsTests(unittest.TestCase):
    def test_rejects_too_many_sections(self) -> None:
        with self.assertRaises(ValidationError):
            validate_model_counts(257, 10)

    def test_rejects_too_many_options(self) -> None:
        with self.assertRaises(ValidationError):
            validate_model_counts(10, 8193)


class IntegrationTests(unittest.TestCase):
    def test_build_model_rejects_oversize(self) -> None:
        with self.assertRaises(ValidationError):
            confkit.build_model(_oversize_text())

    def test_parse_config_values_rejects_oversize(self) -> None:
        model = confkit.build_model("")
        with self.assertRaises(ValidationError):
            confkit.parse_config_values(_oversize_text(), model)

    def test_empty_section_header_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            confkit.build_model("[dxvk]\n[]\ndxvk.hud = \"fps\"\n")


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(ValidateTextTests)
    suite.addTests(loader.loadTestsFromTestCase(ValidateSectionTests))
    suite.addTests(loader.loadTestsFromTestCase(ValidateCountsTests))
    suite.addTests(loader.loadTestsFromTestCase(IntegrationTests))
    runner = unittest.TextTestRunner(verbosity=2)
    return 0 if runner.run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
