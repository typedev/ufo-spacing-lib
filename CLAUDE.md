# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UFO Spacing Library is a framework-agnostic Python library for managing font spacing (kerning and margins) with full undo/redo support. It's designed to work with UFO-compatible font objects and can be integrated into any font editor.

## Common Commands

```bash
# Install for development (with uv - recommended)
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_kerning_commands.py -v

# Run single test
uv run pytest tests/test_kerning_commands.py::TestSetKerningCommand::test_set_kerning -v

# Run group commands tests
uv run pytest tests/test_groups_commands.py -v

# Linting
uv run ruff check src/ tests/
uv run ruff check --fix src/ tests/

# Type checking
uv run mypy src/

# Build package
uv build
```

## Architecture

### Command Pattern
The library uses the Command pattern for all font modifications:
- `Command` (ABC in `commands/base.py`) - base class with `execute()`, `undo()`, and `description`
- `CommandResult` - frozen dataclass for operation results with `ok()` and `error()` factories
- All commands store previous state during `execute()` to enable undo

### Core Components

**FontContext** (`contexts.py`): Wraps one or more fonts for operations
- Supports multi-font operations with per-font scaling (for interpolation)
- Factory methods: `from_single_font()`, `from_linked_fonts()`

**Editors** (`editors/`): Command executors with undo/redo history
- `SpacingEditor` - **unified editor** for kerning, groups, and margins (recommended)
- `KerningEditor` and `MarginsEditor` - separate editors (legacy)
- All editors maintain undo/redo stacks and support event callbacks: `on_change`, `on_undo`, `on_redo`

**FontGroupsManager** (`groups_core.py`): Manages kerning/margins groups
- Maintains reverse mappings (glyph → group) for O(1) lookups
- Handles kerning automatically when modifying groups (creating exceptions, merging)
- Key methods: `get_group_for_glyph()`, `add_glyphs_to_group()`, `remove_glyphs_from_group()`

**KernPairInfo** (`groups_core.py`): Dataclass returned by `resolve_kern_pair()`
- Properties: `left`, `right`, `value`, `is_exception`, `left_group`, `right_group`
- Helper properties: `exception_side`, `is_left_exception`, `is_right_exception`, `is_orphan`

**VirtualFont** (`virtual.py`): Font-like wrapper for preview/simulation
- Isolates kerning/groups changes from source font (for "what-if" scenarios)
- Glyph access delegates to source font (live data)
- Factory: `VirtualFont.from_font(font)` creates copy of kerning/groups with reference to font
- Diff tracking: `get_kerning_diff()`, `get_groups_diff()`, `has_changes()`
- Apply changes: `apply_to(font)` writes changes to real font
- Reset: `reset()`, `reset_kerning()`, `reset_groups()`

**Group Commands** (`commands/groups.py`): Undoable group operations
- `AddGlyphsToGroupCommand` - add glyphs to kerning group with automatic kerning handling
- `RemoveGlyphsFromGroupCommand` - remove glyphs, creating exception pairs
- `DeleteGroupCommand` - delete group, preserving kerning as exceptions
- `RenameGroupCommand` - rename group, updating all kerning references
- All commands store kerning state (pairs with values) for complete undo/redo

**MetricsRulesManager** (`rules_manager.py`): GlyphsApp-like metrics keys system
- Manages linked sidebearings with automatic cascade updates
- Rules stored in `font.lib["com.typedev.spacing.metricsRules"]` with version metadata
- Supported syntax: `=A` (copy), `=A+10` (arithmetic), `=|` (symmetry), `=H|` (opposite side)
- Validation via `manager.validate()` returns `ValidationReport` with unified `RuleIssue` list
- Cascade order computed via topological sort for correct update order
- Key methods: `set_rule()`, `get_rule()`, `remove_rule()`, `evaluate()`, `get_cascade_order()`

**Rule Commands** (`commands/rules.py`): Undoable rule operations
- `SetMetricsRuleCommand` - set or update a metrics rule
- `RemoveMetricsRuleCommand` - remove a metrics rule
- `SyncRulesCommand` - batch synchronization of all rules (for deferred updates)
- All support undo/redo and multi-font contexts

**Rules Generator** (`rules_generator.py`): Generate rules from composite structure
- `generate_rules_from_composites(font)` - analyzes composites and returns `RuleGenerationResult`
- Component 0 (index 0) determines both left and right margins
- Returns rules dict + issues list (warnings for edge cases like component extends beyond base)

**Unified Issue Reporting** (`rules_core.py`): Common issue format for validation and generation
- `RuleIssue` dataclass with `glyph`, `code`, `message`, `severity`, `details`
- Issue codes: `E01`/`E02` (errors), `W01`-`W08` (warnings), `I01` (info)
- Factory functions: `create_cycle_error()`, `create_missing_glyph_warning()`, etc.
- Used by both `ValidationReport` and `RuleGenerationResult`

### Group Naming Conventions
- Kerning groups: `public.kern1.*` (left side), `public.kern2.*` (right side)
- Margins groups: `com.typedev.margins1.*`, `com.typedev.margins2.*`

### Font Interface Requirements
The library expects font objects with:
- `font.kerning` - dict-like with `__getitem__`, `__setitem__`, `__delitem__`, `__contains__`, `get()`, `remove()`
- `font.groups` - dict-like for group management
- `font.lib` - dict-like for storing metrics rules and metadata
- `font[glyph_name]` - access to glyph objects with `leftMargin`, `rightMargin`, `width` attributes
- See `tests/mocks.py` for mock implementations

### Metrics Rules Integration
Margin commands (`SetMarginCommand`, `AdjustMarginCommand`) have `apply_rules=True` by default:
- When margin changes, dependent glyphs are automatically updated via cascade
- Full undo/redo support for both main change and cascade effects
- Set `apply_rules=False` to skip cascade (e.g., for manual overrides)
- SpacingEditor automatically provides rules managers to margin commands

## Key Design Decisions

- Commands use `id(font)` as dictionary keys since font objects may not be hashable
- History is unlimited by default; call `clear_history()` to free memory in long sessions
- All public methods have camelCase aliases for backward compatibility (e.g., `get_group_for_glyph` / `getGroupNameByGlyph`)

## Language Policy

- All code comments, documentation and commits in English
- Variable and function names in English
- Chat/communication can be in any language

