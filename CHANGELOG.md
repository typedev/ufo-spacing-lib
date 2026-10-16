# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-10-16

### Added
- Margin planner (`ufo_spacing_lib.planner`): a pure planner that returns every
  change a margin edit implies without touching the font.
  - `plan_margin_edit(source, glyph, side, delta=|value=, rules=, reverse_map=,
    margins=, round_values=)` and `plan_sync(source, rules, names=)` return a
    `Plan` (`changes`, `names`, `issues`); `apply_plan(source, plan)` applies it;
    `Plan.inverted()` undoes it.
  - `check_rules(source, rules, names=)` returns a `RulesStatus` with
    out-of-sync glyph sides (`OutOfSync`) and validation issues.
  - Composites built on a glyph whose contents shift are always held in place,
    transform-aware (mirrored, scaled, rotated components). A rule's contents
    shift is itself a shift event, so nested composites follow their rules and
    stay intact.
  - Everything works on a glyph source (font or layer); no `font.lib` access.
  - Float-safe: rule results are not rounded unless `round_values=True`.
  - Pluggable margin reader (`margins=`), with `upright_margins` and
    `angled_margins(source, italic_angle)`.
  - `build_reverse_component_map(source)` and `component_shift()`.
- `MetricsRulesManager(rules=..., source=..., autosave=...)` and
  `MetricsRulesManager.from_rules(rules, source)`: a manager built from a rules
  dict on any glyph source. New `save()` and `get_parsed_rule()`.
- `ParsedRule.apply()` and `ParsedRule.source_side_for()`.
- `evaluate(..., rounded=False)` returns the exact value.
- Issue codes: `W09` multi-body candidate (generator), `W10` edit overrides
  the glyph's own rule, `W11` glyph without outline, `W12` rule cannot be
  evaluated (division by zero).
- Generator: `RuleGenerationResult.alternatives` holds a geometric proposal
  (left from the component with the smallest xMin, right from the one with the
  largest xMax) when it differs from component 0, with a `W09` issue carrying
  both proposals. `RuleGenerationResult.skip_reasons` explains every skipped
  glyph.
- Margin commands: `plan_for(font, context, rules_manager)` previews a command.

### Changed
- `SetMarginCommand`, `AdjustMarginCommand` and `SyncRulesCommand` are thin
  wrappers over the planner. Undo applies the inverted plan.
- **Behaviour:** without a rule, composites no longer follow a left-margin edit
  of their base; they stay in place. With a rule, they follow it.
- `propagate_to_composites` and `recursive_propagate` are deprecated no-ops
  (a `DeprecationWarning` is raised when set).
- `SpacingEditor.get_affected_glyphs_preview()` uses the planner and returns
  exactly the glyphs `execute()` changes.
- Generator: component bounds use the full transformation; mixed composites are
  detected by contour count when the glyph exposes one; it accepts a layer.
- Rule command results now carry rule issues as `warnings`.

### Fixed
- A single-component composite lost its component offset on a left edit of its
  base.
- Editing a non-base component moved it twice and never moved the composite's
  anchors and own contours.
- Scaled, mirrored and rotated components were shifted by the raw delta.
- Undo restored composites before their base, restored margins only (not width
  or component offsets) and left composites broken.
- Angled left `SetMarginCommand` did not change the width.
- `SetMarginCommand` on an empty glyph used the whole value as the width.
- Margin commands only work through `name in font` / `font[name]`, so a layer
  can stand in for a font.
- A composite whose rule points at another glyph no longer receives a
  propagation shift that fights the rule.

## [0.4.3] - 2026-09-24

### Fixed
- `VirtualFont.keys()` now returns a `list` as declared, instead of the source
  font's keys view or tuple.
- Type annotations: the package now passes `mypy` with no errors.

### Changed
- CI runs ruff, mypy and tests on Python 3.10-3.14 for every push and pull request.
- Declared Python 3.13 and 3.14 support in classifiers.

## [0.4.2] - 2026-09-24

### Fixed
- `resolve_kern_pair()` now checks glyph+group before group+glyph, matching the
  UFO kerning spec and `fontTools.ufoLib.kerning.lookupKerningValue`. Previously a
  pair covered by both kinds of exception resolved to the wrong key and value.

### Changed
- Added `fonttools` to the `dev` extra so the italic margins tests run.
- Releases are published to PyPI from GitHub Actions via trusted publishing.

## [0.4.0] - 2026-01-12

### Added
- Rules generator: `generate_rules_from_composites()` analyzes composite glyphs and generates metrics rules
- `RuleGenerationResult` with rules dict, issues list, and skipped glyphs
- Unified issue reporting system with `RuleIssue` dataclass
- Issue codes: E01-E02 (errors), W01-W08 (warnings), I01 (info)
- Factory functions for creating issues (`create_cycle_error`, `create_missing_glyph_warning`, etc.)
- `SyncRulesCommand` for batch synchronization of all rules
- Makefile for build/publish workflow
- bump2version configuration for version management

### Changed
- `ValidationReport` and `RuleGenerationResult` now use unified `RuleIssue` list
- Exported `RuleIssue` and all issue codes from main module

## [0.3.0] - 2026-01-12

### Added
- Metrics rules system for linked sidebearings
- `MetricsRulesManager` for managing rules with automatic cascade updates
- Rule syntax: `=A` (copy), `=A+10` (arithmetic), `=|` (symmetry), `=H|` (opposite side)
- `SetMetricsRuleCommand` and `RemoveMetricsRuleCommand`
- Validation with cycle detection, missing glyph warnings
- Cascade order computed via topological sort
- `apply_rules` parameter in margin commands for automatic propagation

### Fixed
- Rules take priority over composite propagation

## [0.2.0] - 2026-01-10

### Added
- Undo/redo support for kerning group operations
- `AddGlyphsToGroupCommand` - add glyphs to kerning group with automatic kerning handling
- `RemoveGlyphsFromGroupCommand` - remove glyphs, creating exception pairs
- `DeleteGroupCommand` - delete group, preserving kerning as exceptions
- `RenameGroupCommand` - rename group, updating all kerning references
- `SpacingEditor` - unified editor for kerning, groups, and margins
- `VirtualFont` for preview/simulation of font changes
- Diff tracking: `get_kerning_diff()`, `get_groups_diff()`, `has_changes()`

### Changed
- Renamed `ExceptionSide.GLYPH_PAIR` to `DIRECT_KEY` for clarity

## [0.1.1] - 2026-01-08

### Changed
- Improved documentation
- Renamed `ExceptionSide.GLYPH_PAIR` to `DIRECT_KEY`

## [0.1.0] - 2026-01-07

### Added
- Initial release
- `KerningEditor` and `MarginsEditor` with undo/redo support
- Kerning commands: `SetKerningCommand`, `AdjustKerningCommand`, `RemoveKerningCommand`, `CreateExceptionCommand`
- Margins commands: `SetMarginCommand`, `AdjustMarginCommand`
- `FontGroupsManager` for kerning/margins groups management
- `FontContext` for single and multi-font operations
- `KernPairInfo` dataclass with `resolve_kern_pair()` function
