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
- `KerningEditor` and `MarginsEditor` have identical APIs
- Maintain separate undo/redo stacks
- Support event callbacks: `on_change`, `on_undo`, `on_redo`

**FontGroupsManager** (`groups_core.py`): Manages kerning/margins groups
- Maintains reverse mappings (glyph → group) for O(1) lookups
- Handles kerning automatically when modifying groups (creating exceptions, merging)
- Key methods: `get_group_for_glyph()`, `add_glyphs_to_group()`, `remove_glyphs_from_group()`

**KernPairInfo** (`groups_core.py`): Dataclass returned by `resolve_kern_pair()`
- Properties: `left`, `right`, `value`, `is_exception`, `left_group`, `right_group`
- Helper properties: `exception_side`, `is_left_exception`, `is_right_exception`, `is_orphan`

### Group Naming Conventions
- Kerning groups: `public.kern1.*` (left side), `public.kern2.*` (right side)
- Margins groups: `com.typedev.margins1.*`, `com.typedev.margins2.*`

### Font Interface Requirements
The library expects font objects with:
- `font.kerning` - dict-like with `__getitem__`, `__setitem__`, `__delitem__`, `__contains__`, `get()`, `remove()`
- `font.groups` - dict-like for group management
- `font[glyph_name]` - access to glyph objects with `leftMargin`, `rightMargin`, `width` attributes
- See `tests/mocks.py` for mock implementations

## Key Design Decisions

- Commands use `id(font)` as dictionary keys since font objects may not be hashable
- History is unlimited by default; call `clear_history()` to free memory in long sessions
- All public methods have camelCase aliases for backward compatibility (e.g., `get_group_for_glyph` / `getGroupNameByGlyph`)

## Language Policy

- All code comments, documentation and commits in English
- Variable and function names in English
- Chat/communication can be in any language

