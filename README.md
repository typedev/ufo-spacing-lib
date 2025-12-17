# UFO Spacing Library

A framework-agnostic Python library for managing font spacing (kerning and margins) with full undo/redo support. Designed to work with UFO-compatible font objects.

## Features

- **Framework Independent**: Works with any font editor that provides compatible font objects
- **Undo/Redo Support**: Full command pattern implementation with unlimited history
- **Multi-Font Operations**: Support for linked/interpolated fonts with per-font scaling
- **Composite Propagation**: Automatic margin propagation to composite glyphs
- **Well Documented**: Comprehensive docstrings and type hints throughout

## Installation

```bash
# From the repository root
pip install -e ./source/ufo_spacing_lib

# Or copy the ufo_spacing_lib folder to your project
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

## Architecture

```
ufo_spacing_lib/
├── __init__.py          # Main exports
├── contexts.py          # FontContext class
├── groups_core.py       # FontGroupsManager, KernPairInfo, resolve_kern_pair
├── commands/
│   ├── __init__.py
│   ├── base.py          # Command ABC, CommandResult
│   ├── kerning.py       # Kerning commands
│   └── margins.py       # Margins commands
├── editors/
│   ├── __init__.py
│   ├── kerning.py       # KerningEditor
│   └── margins.py       # MarginsEditor
└── tests/
    ├── __init__.py
    ├── mocks.py         # MockFont, MockGlyph, etc.
    ├── test_kerning_commands.py
    ├── test_editors.py
    └── test_groups_manager.py
```

## Font Object Interface

The library is designed to work with any font object that implements this interface:

### For Kerning Operations

```python
class FontKerning:
    """Dict-like kerning access."""
    def __getitem__(self, pair: Tuple[str, str]) -> int: ...
    def __setitem__(self, pair: Tuple[str, str], value: int): ...
    def __delitem__(self, pair: Tuple[str, str]): ...
    def __contains__(self, pair: Tuple[str, str]) -> bool: ...
    def get(self, pair: Tuple[str, str], default=None) -> Optional[int]: ...

class Font:
    kerning: FontKerning
```

### For Margins Operations

```python
class Glyph:
    leftMargin: Optional[int]
    rightMargin: Optional[int]
    width: int
    components: List[Component]  # Optional
    
    def moveBy(self, delta: Tuple[int, int]): ...
    def changed(self): ...  # Optional

class Component:
    offset: Tuple[int, int]
    def moveBy(self, delta: Tuple[int, int]): ...

class Font:
    def __getitem__(self, glyph_name: str) -> Glyph: ...
    def __contains__(self, glyph_name: str) -> bool: ...
    def getReverseComponentMapping(self) -> Dict[str, List[str]]: ...  # Optional
```

## Commands Reference

### Kerning Commands

| Command | Description |
|---------|-------------|
| `SetKerningCommand(pair, value)` | Set kerning to absolute value |
| `AdjustKerningCommand(pair, delta)` | Adjust kerning by delta |
| `RemoveKerningCommand(pair)` | Remove a kerning pair |
| `CreateExceptionCommand(pair, value, side)` | Create kerning exception |

### Margins Commands

| Command | Description |
|---------|-------------|
| `SetMarginCommand(glyph, side, value)` | Set margin to absolute value |
| `AdjustMarginCommand(glyph, side, delta)` | Adjust margin by delta |

All commands support:
- Multi-font operations via `FontContext`
- Per-font scaling
- Full undo/redo

## Testing

The library includes 75+ unit tests covering all components.

```bash
cd source

# Run all tests
python3 -m unittest ufo_spacing_lib.tests.test_kerning_commands \
                    ufo_spacing_lib.tests.test_editors \
                    ufo_spacing_lib.tests.test_groups_manager -v

# Run specific test module
python3 -m unittest ufo_spacing_lib.tests.test_kerning_commands -v

# With pytest (if installed)
python3 -m pytest ufo_spacing_lib/tests/ -v
```

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| Kerning Commands | 25 | SetKerning, AdjustKerning, RemoveKerning, CreateException |
| Editors | 20 | KerningEditor, MarginsEditor, undo/redo, callbacks |
| Groups Manager | 30 | FontGroupsManager, add/remove/delete/rename groups |

## License

MIT License

## Author

Alexander Lubovenko 
lubovenko@gmail.com 
github.com/typedev

