"""Runtime boundary validation for the config layer.

Pure standard library. These helpers enforce the *boundaries* a DXVK
configuration document is allowed to cross: source size, single-line length,
section/option counts and section-name shape. They never change parsing
semantics -- valid input passes through untouched; only clearly out-of-bounds
input raises :class:`ValidationError`.

This is the Python-side answer to the "runtime boundary schema" requirement:
the core is dependency-free, so validation is expressed as plain guards rather
than pulling in pydantic/msgspec.
"""

from __future__ import annotations

# Trusted maxima for a normal dxvk.conf / reference document. A reference file
# ships a few dozen options across a handful of sections; the limits below
# leave generous headroom while still rejecting pathological input that would
# otherwise allocate unbounded memory.
MAX_CONF_BYTES = 1 * 1024 * 1024  # 1 MiB of source text
MAX_LINE_LENGTH = 8192  # one logical line
MAX_SECTIONS = 256
MAX_OPTIONS = 8192
MAX_SECTION_NAME = 64


class ValidationError(ValueError):
    """Raised when input violates a configured boundary for a DXVK config."""


def validate_conf_text(text: str) -> None:
    """Validate raw config/reference text before parsing.

    Raises :class:`ValidationError` on out-of-bounds input. Valid input passes
    through unchanged.
    """
    if not isinstance(text, str):
        raise ValidationError(f"config text must be str, got {type(text).__name__}")
    size = len(text.encode("utf-8", "replace"))
    if size > MAX_CONF_BYTES:
        raise ValidationError(
            f"config text too large: {size} bytes exceeds limit of {MAX_CONF_BYTES}"
        )
    for index, line in enumerate(text.splitlines(), start=1):
        length = len(line)
        if length > MAX_LINE_LENGTH:
            raise ValidationError(
                f"line {index} too long: {length} chars exceeds limit of {MAX_LINE_LENGTH}"
            )


def validate_config_values_text(text: str) -> None:
    """Validate a user-supplied dxvk.conf before reading its options back."""
    validate_conf_text(text)


def validate_section_name(name: str, *, line: int = 0) -> None:
    """Reject malformed section headers such as an empty ``[]``."""
    where = f"line {line}: " if line else ""
    if not name:
        raise ValidationError(f"{where}empty section header [] is not valid")
    if len(name) > MAX_SECTION_NAME:
        raise ValidationError(
            f"{where}section name {name!r} too long ({len(name)} > {MAX_SECTION_NAME})"
        )


def validate_model_counts(sections: int, options: int) -> None:
    """Bound the parsed catalogue so a pathological file cannot blow up memory."""
    if sections > MAX_SECTIONS:
        raise ValidationError(f"too many sections: {sections} > {MAX_SECTIONS}")
    if options > MAX_OPTIONS:
        raise ValidationError(f"too many options: {options} > {MAX_OPTIONS}")
