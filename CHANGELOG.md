# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
