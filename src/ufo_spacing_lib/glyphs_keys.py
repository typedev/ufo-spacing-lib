"""
Glyphs.app Metrics Keys.

Converts the metrics keys that glyphsLib keeps in each glyph's lib into
metrics rules, and rules back into Glyphs key text.

glyphsLib (``minimal=False``) writes two levels of keys:

- ``com.schriftgestaltung.Glyphs.glyph.{left,right,width}MetricsKey``: the
  glyph-level key, shared by all masters (copied into every master UFO);
- ``com.schriftgestaltung.Glyphs.layer.{left,right,width}MetricsKey``: the
  master-only key (typed ``==...`` in Glyphs). It overrides the glyph-level
  key for that master.

Example:
    >>> rules, issues = rules_from_glyphs_keys(master_font)
    >>> manager = MetricsRulesManager.from_rules(rules, master_font)
    >>> glyphs_key_from_rule("=H|")
    '=|H'
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .rules_constants import SIDE_LEFT, SIDE_RIGHT, SIDE_WIDTH
from .rules_core import (
    RuleIssue,
    create_ambiguous_name_warning,
    create_missing_glyph_warning,
    create_parse_error,
    create_width_right_conflict_warning,
    format_number,
)
from .rules_parser import RuleParseError, RuleParser

GLYPHS_GLYPH_KEY = "com.schriftgestaltung.Glyphs.glyph.{side}MetricsKey"
GLYPHS_LAYER_KEY = "com.schriftgestaltung.Glyphs.layer.{side}MetricsKey"

_SIDES = (SIDE_LEFT, SIDE_RIGHT, SIDE_WIDTH)


def _names(source: Any) -> list[str]:
    keys = getattr(source, "keys", None)
    if callable(keys):
        return list(keys())
    return [item if isinstance(item, str) else item.name for item in source]


def _key_text(lib: Any, key: str) -> str | None:
    try:
        value = lib.get(key)
    except AttributeError:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def rules_from_glyphs_keys(
    source: Any, glyph_names: Iterable[str] | None = None
) -> tuple[dict[str, dict[str, str]], list[RuleIssue]]:
    """
    Turn the Glyphs metrics keys in glyph libs into metrics rules.

    Per glyph and side, the layer-level key wins over the glyph-level key.
    Rules come back in canonical spelling. Never writes any lib.

    Args:
        source: Glyph source (one master font or layer) whose glyphs carry
            the glyphsLib lib keys.
        glyph_names: Glyphs to read. None means the whole source.

    Returns:
        ``(rules, issues)``: rules as ``{glyph: {side: rule}}`` and issues:
        E01 for a key that does not parse (unsupported Glyphs syntax
        included, with the reason), W01 for a reference to a glyph missing
        from the source, W13 for an ambiguous "=a-5", W14 for a right key
        that yields to a width key. Every issue's details carry ``key``
        (the lib key) and ``level`` ("glyph" or "layer").
    """
    parser = RuleParser()
    names = _names(source) if glyph_names is None else list(glyph_names)
    rules: dict[str, dict[str, str]] = {}
    issues: list[RuleIssue] = []

    for name in names:
        if name not in source:
            continue
        lib = getattr(source[name], "lib", None)
        if lib is None:
            continue

        sides: dict[str, str] = {}
        for side in _SIDES:
            level = "layer"
            key = GLYPHS_LAYER_KEY.format(side=side)
            text = _key_text(lib, key)
            if text is None:
                level = "glyph"
                key = GLYPHS_GLYPH_KEY.format(side=side)
                text = _key_text(lib, key)
            if text is None:
                continue

            origin = {"key": key, "level": level}
            try:
                parsed = parser.parse(text, side)
            except RuleParseError as e:
                issue = create_parse_error(name, side, text, str(e))
                issue.details.update(origin)
                issues.append(issue)
                continue

            rule = parsed.format()
            sides[side] = rule
            if parsed.source_glyph and parsed.source_glyph not in source:
                issue = create_missing_glyph_warning(
                    name, side, rule, parsed.source_glyph
                )
                issue.details.update(origin)
                issues.append(issue)
            if parsed.operator == "-" and parsed.source_glyph:
                whole = f"{parsed.source_glyph}-{format_number(parsed.operand or 0)}"
                if whole in source:
                    issue = create_ambiguous_name_warning(
                        name, side, rule, parsed, whole
                    )
                    issue.details.update(origin)
                    issues.append(issue)

        if SIDE_WIDTH in sides and SIDE_RIGHT in sides:
            issue = create_width_right_conflict_warning(
                name, sides[SIDE_WIDTH], sides[SIDE_RIGHT]
            )
            # Name the key that holds the ignored right rule
            layer_key = GLYPHS_LAYER_KEY.format(side=SIDE_RIGHT)
            if _key_text(lib, layer_key):
                issue.details.update({"key": layer_key, "level": "layer"})
            else:
                issue.details.update(
                    {"key": GLYPHS_GLYPH_KEY.format(side=SIDE_RIGHT), "level": "glyph"}
                )
            issues.append(issue)
        if sides:
            rules[name] = sides

    return rules, issues


def glyphs_key_from_rule(rule: str, side: str = SIDE_LEFT) -> str:
    """
    The Glyphs.app spelling of a rule, for export to a .glyphs file.

    The canonical rule spelling is valid Glyphs syntax: "=A", "=A+10",
    "=|A", "=|A+20", "=|", "=40". A glyph whose name ends like an
    operation ("a-5") is written bare ("a-5"), which Glyphs reads as a
    reference.

    Args:
        rule: Rule text in any accepted spelling.
        side: "left", "right" or "width" (width rejects "=|").

    Raises:
        RuleParseError: If the rule does not parse.
    """
    return RuleParser().format(rule, side)
