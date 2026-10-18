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

# Adjust left margin (composites built on A stay in place;
# they follow A only through metrics rules)
cmd = AdjustMarginCommand(
    glyph_name='A',
    side='left',
    delta=10,
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

### Group Operations with Undo/Redo

```python
from ufo_spacing_lib import (
    SpacingEditor,
    FontContext,
    FontGroupsManager,
    AddGlyphsToGroupCommand,
    RemoveGlyphsFromGroupCommand,
    AdjustKerningCommand,
)

# SpacingEditor provides unified undo/redo for kerning AND groups
editor = SpacingEditor()
context = FontContext.from_single_font(font)
manager = FontGroupsManager(font)

# Execute kerning command
cmd1 = AdjustKerningCommand(pair=('A', 'V'), delta=-10)
editor.execute(cmd1, context)

# Execute group command (same editor, same history!)
cmd2 = AddGlyphsToGroupCommand(
    group_name='public.kern1.A',
    glyphs=['Aacute', 'Agrave'],
    groups_manager=manager,
    check_kerning=True,  # Automatically handles kerning exceptions
)
editor.execute(cmd2, context)

# Undo works across both kerning and groups
editor.undo()  # Undoes group command
editor.undo()  # Undoes kerning command
editor.redo()  # Redoes kerning command
editor.redo()  # Redoes group command
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

## Metrics Rules (Linked Sidebearings)

Metrics keys system for linking sidebearings between glyphs.

### Basic Usage

```python
from ufo_spacing_lib import MetricsRulesManager, SpacingEditor, FontContext

# Create manager
manager = MetricsRulesManager(font)

# Set rules: Aacute.left = A.left, Aacute.right = A.right
manager.set_rule("Aacute", "left", "=A")
manager.set_rule("Aacute", "right", "=A")

# Arithmetic operations
manager.set_rule("B", "left", "=A+10")   # A.left + 10
manager.set_rule("C", "right", "=A*0.5") # A.right * 0.5

# Symmetry: right = left of same glyph
manager.set_rule("H", "right", "=|")

# Opposite side from another glyph (Glyphs.app form; "=A|" also accepted)
manager.set_rule("B", "right", "=|A")    # B.right = A.left
manager.set_rule("B", "left", "=|A+20")  # B.left = A.right + 20

# Constant, and width rules (advance width)
manager.set_rule("space", "width", "=250")
manager.set_rule("zero.tf", "width", "=zero.tf.base")
```

The syntax is compatible with Glyphs.app metrics keys: glyph names may contain
`-` (`=a-cy+10`), a bare name means a reference (`A` is `=A`), `==` is read as
`=`, and spaces around the operator are allowed. Unsupported Glyphs forms
(`=A@200`, `=+10`, parentheses, `=H+O`) give a parse error with the reason.
Rules are stored in canonical spelling (`=|H`, `=H+10`).

Rules can be measured at a height, as Glyphs' `@` keys: `=d@200+5` reads `d`'s
right margin along the line y = 200 and measures the target there too, which
is what glyphs without a stable extreme (`dcroat`) need. The library's reader
(`margin_reader(source, italic_angle)`) does this with a beam that follows the
slant in italic. A custom reader may take a third `at_height` argument;
two-argument readers skip rules with a height (W16).

A width rule takes precedence over a right rule on the same glyph (W14). A left
edit keeps the width; a right edit breaks the width rule.

### Glyphs.app Metrics Keys

```python
from ufo_spacing_lib import glyphs_key_from_rule, rules_from_glyphs_keys

# Keys kept by glyphsLib in each glyph's lib; per side, the layer key wins
rules, issues = rules_from_glyphs_keys(master_font)
glyphs_key_from_rule("=H|")  # "=|H"
```

### Validation

```python
from ufo_spacing_lib import E_CYCLE, W_MISSING_GLYPH

report = manager.validate()

if not report.is_valid:
    for error in report.errors:
        print(f"Error [{error.code}]: {error.message}")

for warning in report.warnings:
    print(f"Warning [{warning.code}]: {warning.message}")

# Filter by specific code
cycles = report.get_issues_by_code(E_CYCLE)
missing = report.get_issues_by_code(W_MISSING_GLYPH)
```

### Cascade Updates

```python
# When A changes, all dependents update automatically
editor = SpacingEditor()
context = FontContext.from_single_font(font)

# This updates A and all glyphs with rules referencing A
cmd = SetMarginCommand(glyph_name="A", side="left", value=50)
editor.execute(cmd, context)

# Deferred sync: change without cascade, then sync all at once
cmd1 = SetMarginCommand(glyph_name="A", side="left", value=50, apply_rules=False)
cmd2 = SetMarginCommand(glyph_name="B", side="left", value=40, apply_rules=False)
editor.execute(cmd1, context)
editor.execute(cmd2, context)

# Sync all rules
from ufo_spacing_lib import SyncRulesCommand
sync_cmd = SyncRulesCommand()
editor.execute(sync_cmd, context)
```

### Margin Planner

A pure planner for applications that keep their own undo. It returns every
change an edit implies, without touching the font, and works on any glyph
source (a font or a layer: `name in source` and `source[name]`).

```python
from ufo_spacing_lib import apply_plan, check_rules, plan_margin_edit, plan_sync

rules = {"Aacute": {"left": "=A", "right": "=A"}}  # or a MetricsRulesManager

plan = plan_margin_edit(layer, "A", "left", delta=10, rules=rules)
plan.names      # every glyph to snapshot before applying
plan.changes    # GlyphChange per glyph: shift, width_delta, component_offsets, reasons
plan.issues     # RuleIssue list; planning never raises for rule problems

apply_plan(layer, plan)
apply_plan(layer, plan.inverted())  # exact undo

# Bring ruled glyphs in line, and report glyphs out of sync
apply_plan(layer, plan_sync(layer, rules))
status = check_rules(layer, rules)
for entry in status.out_of_sync:
    print(entry.glyph, entry.side, entry.rule, entry.expected, entry.actual)
```

How an edit cascades:

1. Composites that use a glyph whose contents shift get the opposite offset
   on that component, so they stay pixel-for-pixel in place. This is
   transform-aware: a mirrored component gets `+d`, a rotated one gets a
   vertical correction.
2. Rules then run in dependency order. A left-side rule shifts the glyph's
   whole contents and its advance, and that shift is itself compensated in the
   composites built on it. A right-side rule changes the advance only.

Broken (dormant) rules: an edit on a ruled side reports the side in
`plan.breaks`. Mark it with `manager.mark_broken(glyph, side)` and the rule
stays dormant: planner, sync and cascade skip it, and `check_rules` lists it
in `status.broken`. To bring it back, call `manager.restore_rule(glyph, side)`,
then apply `plan_restore(source, manager, glyph, side)`. Flags are stored next
to the rules as `"broken": {glyph: [sides]}`.

Manual sides: `manager.mark_manual(glyph, side)` says a side without a rule
follows nothing (sides `left`, `right`, `width`, or `both`). A side has either
a rule (active or broken) or a manual marker: `mark_manual` on a ruled side
returns False, and `set_rule` clears the marker. The planner treats a manual
side as any side without a rule (compensation only); `check_rules` and
`plan_sync` ignore it; `validate()` warns (W17) about a marker on a glyph the
source does not have. Read them with `is_manual(glyph, side=None)` and
`get_manual()`, clear one with `clear_manual(glyph, side)`. Stored as
`"manual": {glyph: [sides]}` (since 0.9.0).

Pass `margins=angled_margins(source, italic_angle)` (or your own
`(glyph, side) -> float | None`) to read and target angled margins. Rule results
are not rounded unless `round_values=True`.

### Generate Rules from Composites

> **Deprecated since 0.9.0**: rule generation from composite structure will be
> removed in a future release; calling it emits a `DeprecationWarning`.

```python
from ufo_spacing_lib import generate_rules_from_composites, I_SINGLE_COMPONENT

# Analyze composite glyphs and generate rules
result = generate_rules_from_composites(font)

# Generated rules based on component 0 (base)
for glyph, sides in result.rules.items():
    print(f"{glyph}: left={sides['left']}, right={sides['right']}")
    # e.g., "Aacute: left==A, right==A"

# Check issues (warnings, info)
for issue in result.issues:
    print(f"[{issue.code}] {issue.glyph}: {issue.message}")

# Filter by severity
warnings = result.warnings  # Only warnings
infos = result.infos        # Only info messages

# Single component info
single = result.get_issues_by_code(I_SINGLE_COMPONENT)

# Multi-body composites (DZ, f_i) and overhanging accents: a geometric
# proposal from the outermost components, offered next to the default
result.alternatives   # {"DZ": {"left": "=D", "right": "=Z"}}
result.skip_reasons   # {"Abar": "mixed_contours"}
```

### Issue Codes

| Code | Severity | Description |
|------|----------|-------------|
| `E01` | Error | Parse error in rule syntax |
| `E02` | Error | Circular dependency detected |
| `W01` | Warning | References missing glyph |
| `W02` | Warning | Self-reference detected |
| `W03` | Warning | Component wider than base |
| `W04` | Warning | Component extends left of base |
| `W05` | Warning | Component extends right of base |
| `W06` | Warning | Base component has zero width |
| `W07` | Warning | Mixed contours and components |
| `W08` | Warning | Base component does not exist |
| `W09` | Warning | Outermost components differ from component 0 (multi-body candidate) |
| `W10` | Warning | A direct edit overrides the glyph's own rule |
| `W11` | Warning | Glyph has no outline (edit or rule target/source) |
| `W12` | Warning | Rule cannot be evaluated (division by zero) |
| `W13` | Warning | `=a-5` reads as `a` minus 5, but a glyph `a-5` exists |
| `W14` | Warning | Right rule ignored: the width rule takes precedence |
| `W15` | Warning | No outline at the rule's height (target or source) |
| `W16` | Warning | The margin reader cannot measure at a height |
| `W17` | Warning | Manual marker on a glyph the source does not have |
| `I01` | Info | Single component composite |

---

## API Reference

### Editors

| Class | Description |
|-------|-------------|
| `SpacingEditor` | **Unified editor** for kerning, margins, and groups (recommended) |
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

#### Group Commands

| Command | Parameters | Description |
|---------|------------|-------------|
| `AddGlyphsToGroupCommand` | `group_name`, `glyphs`, `groups_manager`, `check_kerning=True` | Add glyphs to a kerning group |
| `RemoveGlyphsFromGroupCommand` | `group_name`, `glyphs`, `groups_manager`, `check_kerning=True` | Remove glyphs from a group |
| `DeleteGroupCommand` | `group_name`, `groups_manager`, `check_kerning=True` | Delete entire group |
| `RenameGroupCommand` | `old_name`, `new_name`, `groups_manager`, `check_kerning=True` | Rename a group |

#### Margins Commands

| Command | Parameters | Description |
|---------|------------|-------------|
| `SetMarginCommand` | `glyph_name`, `side`, `value`, `apply_rules=True` | Set margin to absolute value |
| `AdjustMarginCommand` | `glyph_name`, `side`, `delta`, `apply_rules=True` | Adjust margin by delta |

#### Rules Commands

| Command | Parameters | Description |
|---------|------------|-------------|
| `SetMetricsRuleCommand` | `glyph_name`, `side`, `rule` | Set a metrics rule |
| `RemoveMetricsRuleCommand` | `glyph_name`, `side` | Remove a metrics rule |
| `SyncRulesCommand` | - | Synchronize all rules (batch update) |

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

### Metrics Rules

| Class/Function | Description |
|----------------|-------------|
| `MetricsRulesManager` | Manages metrics rules for linked sidebearings |
| `ValidationReport` | Result of validating rules |
| `RuleIssue` | Unified issue (error/warning/info) |
| `RuleGenerationResult` | Result of generating rules from composites |
| `generate_rules_from_composites(font)` | Generate rules from composite structure |

**MetricsRulesManager Methods:**
- `set_rule(glyph, side, rule)` - Set a rule
- `get_rule(glyph, side)` - Get rule string
- `remove_rule(glyph, side)` - Remove a rule
- `has_rule(glyph, side=None)` - Check if rule exists
- `validate()` → `ValidationReport` - Validate all rules
- `evaluate(glyph, side)` - Calculate value from rule
- `get_cascade_order(glyph, side)` - Get update order for dependents
- `get_dependents(glyph)` - Get glyphs depending on this glyph
- `get_dependencies(glyph)` - Get glyphs this glyph depends on

**ValidationReport Properties:**
- `is_valid` - True if no critical errors
- `issues` - All issues (errors, warnings, info)
- `errors` - Critical errors only
- `warnings` - Warnings only
- `get_issues_by_code(code)` - Filter by issue code
- `get_issues_for_glyph(glyph)` - Filter by glyph

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
├── rules_core.py        # RuleIssue, ValidationReport, issue codes
├── rules_manager.py     # MetricsRulesManager for linked sidebearings
├── rules_parser.py      # Rule syntax parser
├── rules_generator.py   # Generate rules from composites
├── commands/
│   ├── __init__.py
│   ├── base.py          # Command ABC, CommandResult
│   ├── kerning.py       # Kerning commands
│   ├── groups.py        # Group commands (Add, Remove, Delete, Rename)
│   ├── margins.py       # Margins commands with rules cascade
│   └── rules.py         # Rules commands (Set, Remove, Sync)
└── editors/
    ├── __init__.py
    ├── spacing.py       # SpacingEditor (unified, recommended)
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

The library includes 328 unit tests covering all components.

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
| Group Commands | 26 | AddGlyphsToGroup, RemoveGlyphsFromGroup, DeleteGroup, RenameGroup |
| Editors | 20 | KerningEditor, MarginsEditor, SpacingEditor, undo/redo, callbacks |
| Groups Manager | 30 | FontGroupsManager, add/remove/delete/rename groups |
| VirtualFont | 27 | Creation, isolation, glyph access, diff tracking, apply/reset |
| **Metrics Rules** | **63** | MetricsRulesManager, validation, cascade, parser |
| **Rules Commands** | **20** | SetMetricsRule, RemoveMetricsRule |
| **Rules Generator** | **19** | generate_rules_from_composites, warnings |
| **SyncRulesCommand** | **9** | Batch synchronization |

---

## License

MIT License

## Author

Alexander Lubovenko
lubovenko@gmail.com
github.com/typedev
