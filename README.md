# UFO Spacing Library

A framework-agnostic Python library for managing font spacing (kerning and margins) with full undo/redo support. Designed to work with UFO-compatible font objects.

## Features

- **Framework Independent**: Works with any font editor that provides compatible font objects
- **Undo/Redo Support**: Full command pattern implementation with unlimited history
- **Multi-Font Operations**: Support for linked/interpolated fonts with per-font scaling
- **Preview/Simulation**: VirtualFont wrapper for testing changes without modifying real font
- **Groups Management**: Full kerning groups support with automatic exception handling
- **Composite Propagation**: Automatic margin propagation to composite glyphs
- **Well Documented**: Comprehensive docstrings and type hints throughout

## Installation

```bash
# From PyPI
pip install ufo-spacing-lib

# From source
pip install -e .

# Or with uv
uv pip install -e .
```

## Quick Start

### Kerning Operations

```python
from ufo_spacing_lib import (
    KerningEditor,
    FontContext,
    AdjustKerningCommand,
    SetKerningCommand,
    RemoveKerningCommand,
)

# Create an editor
editor = KerningEditor()

# Create a context for your font
context = FontContext.from_single_font(font)

# Adjust kerning by a delta
cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
result = editor.execute(cmd, context)

# Set kerning to absolute value
cmd = SetKerningCommand(pair=('A', 'V'), value=-50)
editor.execute(cmd, context)

# Remove a kerning pair
cmd = RemoveKerningCommand(pair=('A', 'V'))
editor.execute(cmd, context)

# Undo/Redo
editor.undo()
editor.redo()
```

### Margins Operations

```python
from ufo_spacing_lib import (
    MarginsEditor,
    FontContext,
    AdjustMarginCommand,
    SetMarginCommand,
)

editor = MarginsEditor()
context = FontContext.from_single_font(font)

# Adjust left margin (propagates to composites by default)
cmd = AdjustMarginCommand(
    glyph_name='A',
    side='left',
    delta=10,
    propagate_to_composites=True
)
editor.execute(cmd, context)

# Set right margin to absolute value
cmd = SetMarginCommand(
    glyph_name='A',
    side='right',
    value=50
)
editor.execute(cmd, context)
```

### Multi-Font Operations (Interpolation)

```python
# Create context for multiple fonts with scaling
context = FontContext.from_linked_fonts(
    fonts=[light_master, regular_master, bold_master],
    primary=regular_master,
    scales={
        light_master: 0.8,
        regular_master: 1.0,
        bold_master: 1.3
    }
)

# Command applies to all fonts with appropriate scaling
cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
editor.execute(cmd, context)
# light_master: -8, regular_master: -10, bold_master: -13
```

### Event Callbacks

```python
def on_kerning_change(command, result):
    print(f"Kerning changed: {command.description}")
    refresh_ui()

editor.on_change = on_kerning_change
editor.on_undo = on_kerning_change
editor.on_redo = on_kerning_change
```

---

## Groups Management

### FontGroupsManager

Manages kerning and margins groups with O(1) reverse lookups and automatic exception handling.

```python
from ufo_spacing_lib import FontGroupsManager, SIDE_LEFT, SIDE_RIGHT

# Create manager from font
manager = FontGroupsManager(font)

# Get group for a glyph
group = manager.get_group_for_glyph('A', SIDE_LEFT)
# Returns: 'public.kern1.A' or 'A' if not in group

# Check if glyph is in a group
is_grouped = manager.is_glyph_in_group('A', SIDE_LEFT)

# Get key glyph for a group (first glyph)
key_glyph = manager.get_key_glyph('public.kern1.A')

# Check if name is a kerning group
is_group = manager.is_kerning_group('public.kern1.A')  # True
is_group = manager.is_kerning_group('A')               # False
```

### Adding/Removing Glyphs from Groups

```python
# Add glyphs to a group
manager.add_glyphs_to_group(
    'public.kern1.A',
    ['Aacute', 'Agrave', 'Atilde'],
    check_kerning=True  # Handles kerning exceptions automatically
)

# Remove glyphs from a group (creates exceptions for existing kerning)
manager.remove_glyphs_from_group(
    'public.kern1.A',
    ['Aacute'],
    create_exceptions=True
)

# Delete entire group
manager.delete_group('public.kern1.A', keep_kerning=False)

# Rename group
manager.rename_group('public.kern1.A', 'public.kern1.A_new')
```

### Kerning Resolution

```python
from ufo_spacing_lib import resolve_kern_pair, KernPairInfo

# Resolve a kerning pair to get full information
info: KernPairInfo = resolve_kern_pair(font, manager, ('A', 'V'))

# KernPairInfo fields:
info.left         # Actual left key in kerning ('A' or 'public.kern1.A')
info.right        # Actual right key in kerning
info.value        # Kerning value (int or None)
info.is_exception # True if this is an exception to group kerning
info.left_group   # Group name for left glyph
info.right_group  # Group name for right glyph

# Computed properties:
info.exception_side    # ExceptionSide enum
info.is_left_exception # True if only left side is exception
info.is_right_exception # True if only right side is exception
info.is_orphan         # True if both sides are exceptions
info.has_value         # True if kerning value exists
```

---

## ExceptionSide Enum

Describes the exception status of a resolved kerning pair.

```python
from ufo_spacing_lib import ExceptionSide

class ExceptionSide(Enum):
    NONE       # Normal group-group pair, not an exception
    LEFT       # Left side is exception (glyph used instead of group)
    RIGHT      # Right side is exception
    BOTH       # Both sides are exceptions (orphan pair)
    DIRECT_KEY # Input was already kerning keys (group names)
```

### Usage Example

```python
info = resolve_kern_pair(font, manager, ('Aacute', 'V'))

match info.exception_side:
    case ExceptionSide.NONE:
        print("Normal group kerning")
    case ExceptionSide.LEFT:
        print(f"Left exception: {info.left} breaks out of {info.left_group}")
    case ExceptionSide.RIGHT:
        print(f"Right exception: {info.right} breaks out of {info.right_group}")
    case ExceptionSide.BOTH:
        print("Orphan pair - both sides are exceptions")
    case ExceptionSide.DIRECT_KEY:
        print("Input was already group names, not glyph names")
```

### Exception Detection for UI

```python
def get_pair_status(font, manager, left, right):
    info = resolve_kern_pair(font, manager, (left, right))

    if not info.is_exception:
        return "normal"

    if info.is_orphan:
        return "orphan"  # Both sides differ from groups

    if info.is_left_exception:
        return f"exception_left:{info.left}"

    if info.is_right_exception:
        return f"exception_right:{info.right}"

    return "normal"
```

---

## VirtualFont (Preview/Simulation)

VirtualFont wraps a real font for testing changes without modifying the source.

```python
from ufo_spacing_lib import VirtualFont, FontContext, AdjustKerningCommand

# Create virtual copy - isolates kerning/groups changes
virtual = VirtualFont.from_font(font)

# Work as usual - changes only affect virtual.kerning/groups
context = FontContext.from_single_font(virtual)
cmd = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
editor.execute(cmd, context)

# Glyphs are live references - changes in font visible through virtual
print(virtual['A'].leftMargin)  # Same as font['A'].leftMargin

# Check what changed
if virtual.has_changes():
    # Get kerning differences
    for pair, (old, new) in virtual.get_kerning_diff().items():
        print(f"{pair}: {old} -> {new}")

    # Get groups differences
    for group, (old, new) in virtual.get_groups_diff().items():
        print(f"{group}: {old} -> {new}")

# Apply to real font when ready
virtual.apply_to(font)

# Or reset to discard all changes
virtual.reset()
virtual.reset_kerning()  # Reset only kerning
virtual.reset_groups()   # Reset only groups
```

---

## API Reference

### Editors

| Class | Description |
|-------|-------------|
| `KerningEditor` | Editor with undo/redo for kerning operations |
| `MarginsEditor` | Editor with undo/redo for margins operations |

**Editor Methods:**
- `execute(command, context)` → `CommandResult` - Execute a command
- `undo()` → `CommandResult | None` - Undo last command
- `redo()` → `CommandResult | None` - Redo last undone command
- `can_undo` / `can_redo` - Check if undo/redo available
- `undo_description` / `redo_description` - Get description of next undo/redo
- `get_history()` → `list[Command]` - Get command history
- `clear_history()` - Clear undo/redo stacks

**Callbacks:**
- `on_change` - Called after execute
- `on_undo` - Called after undo
- `on_redo` - Called after redo

### Commands

#### Kerning Commands

| Command | Parameters | Description |
|---------|------------|-------------|
| `SetKerningCommand` | `pair`, `value` | Set kerning to absolute value |
| `AdjustKerningCommand` | `pair`, `delta`, `remove_zero=True` | Adjust kerning by delta |
| `RemoveKerningCommand` | `pair` | Remove a kerning pair |
| `CreateExceptionCommand` | `pair`, `value=0`, `side='left'` | Create kerning exception |

#### Margins Commands

| Command | Parameters | Description |
|---------|------------|-------------|
| `SetMarginCommand` | `glyph_name`, `side`, `value` | Set margin to absolute value |
| `AdjustMarginCommand` | `glyph_name`, `side`, `delta`, `propagate_to_composites=True` | Adjust margin by delta |

### Contexts

| Class | Description |
|-------|-------------|
| `FontContext` | Wrapper for single or multiple fonts with scaling |

**Factory Methods:**
- `FontContext.from_single_font(font)` - Single font context
- `FontContext.from_linked_fonts(fonts, primary, scales)` - Multi-font with scaling

### Groups Management

| Class/Function | Description |
|----------------|-------------|
| `FontGroupsManager` | Main class for groups management |
| `resolve_kern_pair(font, manager, pair)` | Resolve pair and get full info |
| `KernPairInfo` | Dataclass with resolved pair information |
| `ExceptionSide` | Enum for exception status |

**FontGroupsManager Methods:**
- `get_group_for_glyph(glyph, side)` - Get group name for glyph
- `is_glyph_in_group(glyph, side)` - Check if glyph is in a group
- `get_key_glyph(group)` - Get first glyph of a group
- `is_kerning_group(name)` - Check if name is a kerning group
- `add_glyphs_to_group(group, glyphs, check_kerning)` - Add glyphs
- `remove_glyphs_from_group(group, glyphs, create_exceptions)` - Remove glyphs
- `delete_group(group, keep_kerning)` - Delete a group
- `rename_group(old_name, new_name)` - Rename a group

### Virtual Font

| Class | Description |
|-------|-------------|
| `VirtualFont` | Font wrapper for preview/simulation |
| `VirtualKerning` | Isolated kerning dict |
| `VirtualGroups` | Isolated groups dict |

**VirtualFont Methods:**
- `VirtualFont.from_font(font)` - Create from real font
- `has_changes()` - Check if there are changes
- `get_kerning_diff()` - Get kerning changes dict
- `get_groups_diff()` - Get groups changes dict
- `apply_to(font)` - Apply changes to real font
- `reset()` / `reset_kerning()` / `reset_groups()` - Discard changes

### Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `SIDE_LEFT` | `1` | Left side (kern1, margins1) |
| `SIDE_RIGHT` | `2` | Right side (kern2, margins2) |
| `EDITMODE_OFF` | `0` | Editing disabled |
| `EDITMODE_KERNING` | `1` | Kerning editing mode |
| `EDITMODE_MARGINS` | `2` | Margins editing mode |

---

## Architecture

```
ufo_spacing_lib/
├── __init__.py          # Main exports
├── contexts.py          # FontContext class
├── groups_core.py       # FontGroupsManager, KernPairInfo, resolve_kern_pair
├── virtual.py           # VirtualFont for preview/simulation
├── commands/
│   ├── __init__.py
│   ├── base.py          # Command ABC, CommandResult
│   ├── kerning.py       # Kerning commands
│   └── margins.py       # Margins commands
└── editors/
    ├── __init__.py
    ├── kerning.py       # KerningEditor
    └── margins.py       # MarginsEditor
```

---

## Font Object Interface

The library is designed to work with any font object that implements this interface:

### For Kerning Operations

```python
class FontKerning:
    """Dict-like kerning access."""
    def __getitem__(self, pair: tuple[str, str]) -> int: ...
    def __setitem__(self, pair: tuple[str, str], value: int): ...
    def __delitem__(self, pair: tuple[str, str]): ...
    def __contains__(self, pair: tuple[str, str]) -> bool: ...
    def get(self, pair: tuple[str, str], default=None) -> int | None: ...

class FontGroups:
    """Dict-like groups access."""
    def __getitem__(self, name: str) -> list[str]: ...
    def __setitem__(self, name: str, glyphs: list[str]): ...
    def __delitem__(self, name: str): ...
    def __contains__(self, name: str) -> bool: ...
    def keys(self) -> Iterable[str]: ...

class Font:
    kerning: FontKerning
    groups: FontGroups
```

### For Margins Operations

```python
class Glyph:
    leftMargin: int | None
    rightMargin: int | None
    width: int
    components: list[Component]  # Optional

    def moveBy(self, delta: tuple[int, int]): ...
    def changed(self): ...  # Optional

class Component:
    offset: tuple[int, int]
    def moveBy(self, delta: tuple[int, int]): ...

class Font:
    def __getitem__(self, glyph_name: str) -> Glyph: ...
    def __contains__(self, glyph_name: str) -> bool: ...
    def getReverseComponentMapping(self) -> dict[str, list[str]]: ...  # Optional
```

---

## Testing

The library includes 100+ unit tests covering all components.

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_kerning_commands.py -v

# Run single test
uv run pytest tests/test_groups_manager.py::TestResolvePair -v
```

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| Kerning Commands | 25 | SetKerning, AdjustKerning, RemoveKerning, CreateException |
| Editors | 20 | KerningEditor, MarginsEditor, undo/redo, callbacks |
| Groups Manager | 30 | FontGroupsManager, add/remove/delete/rename groups |
| VirtualFont | 27 | Creation, isolation, glyph access, diff tracking, apply/reset |

---

## License

MIT License

## Author

Alexander Lubovenko
lubovenko@gmail.com
github.com/typedev
