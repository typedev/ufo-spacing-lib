# Metrics Rules Implementation Plan

## Overview

Implementation of GlyphsApp-like metrics keys/rules system for managing linked sidebearings with automatic cascade updates and full undo/redo support.

## Key Decisions

| Aspect | Decision |
|--------|----------|
| Storage | `font.lib["com.typedev.spacing.metricsRules"]` with version metadata |
| Syntax | Basic (`=A`, `=\|`) + arithmetic (`=A+10`, `=A*1.5`) |
| Validation | Explicit from host via `manager.validate()` → `ValidationReport` |
| Multi-font | Each font has own `MetricsRulesManager` |
| Apply rules | Parameter `apply_rules=True` (default) in margin commands |
| Missing glyphs | Ignore + warning in result |
| Runtime modification | Supported, caches rebuild automatically |

## Progress Tracking

- [x] **Phase 1**: Data structures and constants
- [x] **Phase 2**: Rule parser
- [x] **Phase 3**: MetricsRulesManager core
- [x] **Phase 4**: Rule commands
- [x] **Phase 5**: SpacingEditor integration
- [x] **Phase 6**: Margin commands integration
- [x] **Phase 7**: Final testing and documentation

---

## Phase 1: Data Structures and Constants

**Goal**: Define all data classes and constants needed for the system.

### Step 1.1: Create constants module
**File**: `src/ufo_spacing_lib/rules_constants.py`

```python
# Storage key
METRICS_RULES_LIB_KEY = "com.typedev.spacing.metricsRules"
METRICS_RULES_VERSION = 1

# Rule sides
SIDE_LEFT = "left"
SIDE_RIGHT = "right"
SIDE_BOTH = "both"
```

**Test**: Import constants, verify values.

- [ ] Done

### Step 1.2: Create data classes for validation results
**File**: `src/ufo_spacing_lib/rules_core.py`

```python
@dataclass
class ParseError:
    glyph: str
    side: str
    rule: str
    error: str

@dataclass
class MissingGlyphWarning:
    glyph: str
    side: str
    rule: str
    missing_glyph: str

@dataclass
class CycleError:
    cycle: list[str]  # ["A", "B", "A"]

@dataclass
class SelfReferenceWarning:
    glyph: str
    side: str
    rule: str

@dataclass
class ValidationReport:
    is_valid: bool
    cycles: list[CycleError]
    missing_glyphs: list[MissingGlyphWarning]
    parse_errors: list[ParseError]
    self_references: list[SelfReferenceWarning]

    @property
    def warnings(self) -> list[str]: ...

    @property
    def errors(self) -> list[str]: ...
```

**Test**: Create instances, verify properties.

- [ ] Done

### Step 1.3: Create ParsedRule dataclass
**File**: `src/ufo_spacing_lib/rules_core.py` (add to existing)

```python
@dataclass
class ParsedRule:
    """Parsed metrics rule."""
    source_glyph: str | None  # None for "=|" (self-reference)
    source_side: str          # "left", "right", "same" (same as target)
    operator: str | None      # None, "+", "-", "*", "/"
    operand: float | None     # value for operator
    is_symmetry: bool         # True for "=|" pattern
```

**Test**: Create instances with various configurations.

- [ ] Done

### Checkpoint 1
- [ ] All data classes created
- [ ] Unit tests pass for data classes
- [ ] Constants accessible from package

---

## Phase 2: Rule Parser

**Goal**: Parse rule strings like `=A`, `=A+10`, `=|`, `=H|` into `ParsedRule` objects.

### Step 2.1: Create parser module
**File**: `src/ufo_spacing_lib/rules_parser.py`

```python
class RuleParser:
    """Parser for metrics rule syntax."""

    # Regex patterns
    PATTERN_SIMPLE = r"^=([A-Za-z_][A-Za-z0-9_.]*)$"           # =A
    PATTERN_ARITHMETIC = r"^=([A-Za-z_][A-Za-z0-9_.]*)([\+\-\*/])(\d+(?:\.\d+)?)$"  # =A+10
    PATTERN_SYMMETRY = r"^=\|$"                                 # =|
    PATTERN_OPPOSITE = r"^=([A-Za-z_][A-Za-z0-9_.]*)\|$"       # =H|

    def parse(self, rule: str, target_side: str) -> ParsedRule:
        """Parse rule string into ParsedRule."""
        ...

    def validate_syntax(self, rule: str) -> tuple[bool, str | None]:
        """Check if rule has valid syntax. Returns (is_valid, error_message)."""
        ...
```

**Test cases**:
- `=A` → simple reference to glyph A, same side
- `=A+10` → reference + 10 units
- `=A-5` → reference - 5 units
- `=A*1.5` → reference × 1.5
- `=|` → symmetry (RSB = LSB of same glyph)
- `=H|` → opposite side of H (LSB of target = RSB of H)
- Invalid: `=`, `=+10`, `==A`, `A`, empty string

- [ ] Done

### Step 2.2: Write comprehensive parser tests
**File**: `tests/test_rules_parser.py`

```python
class TestRuleParser:
    def test_simple_reference(self): ...
    def test_arithmetic_plus(self): ...
    def test_arithmetic_minus(self): ...
    def test_arithmetic_multiply(self): ...
    def test_arithmetic_divide(self): ...
    def test_symmetry_self(self): ...
    def test_opposite_side(self): ...
    def test_invalid_empty(self): ...
    def test_invalid_no_equals(self): ...
    def test_invalid_double_equals(self): ...
    def test_glyph_with_dot(self): ...  # zero.lf
    def test_glyph_with_underscore(self): ...
```

- [ ] Done

### Checkpoint 2
- [ ] Parser handles all valid syntax
- [ ] Parser rejects invalid syntax with clear errors
- [ ] All parser tests pass

---

## Phase 3: MetricsRulesManager Core

**Goal**: Create the main manager class for rules with caching and validation.

### Step 3.1: Create manager skeleton
**File**: `src/ufo_spacing_lib/rules_manager.py`

```python
class MetricsRulesManager:
    def __init__(self, font):
        self._font = font
        self._parser = RuleParser()
        self._rules: dict[str, dict[str, str]] = {}
        self._parsed_cache: dict[str, dict[str, ParsedRule]] = {}
        self._dependents_cache: dict[str, set[str]] = {}

        self._load_from_font()
        self._rebuild_caches()
```

**Test**: Create manager with empty font, verify initialization.

- [ ] Done

### Step 3.2: Implement load/save methods
```python
def _load_from_font(self) -> None:
    """Load rules from font.lib."""
    data = self._font.lib.get(METRICS_RULES_LIB_KEY)
    if data and data.get("version") == METRICS_RULES_VERSION:
        self._rules = data.get("rules", {})

def _save_to_font(self) -> None:
    """Save rules to font.lib."""
    self._font.lib[METRICS_RULES_LIB_KEY] = {
        "version": METRICS_RULES_VERSION,
        "rules": self._rules
    }
```

**Test**: Load from mock font, save and verify persistence.

- [ ] Done

### Step 3.3: Implement cache building
```python
def _rebuild_caches(self) -> None:
    """Rebuild parsed rules and dependency caches."""
    self._parsed_cache.clear()
    self._dependents_cache.clear()

    for glyph, sides in self._rules.items():
        self._parsed_cache[glyph] = {}
        for side, rule in sides.items():
            try:
                parsed = self._parser.parse(rule, side)
                self._parsed_cache[glyph][side] = parsed

                # Build reverse dependency
                if parsed.source_glyph:
                    self._dependents_cache.setdefault(
                        parsed.source_glyph, set()
                    ).add(glyph)
            except ParseError:
                pass  # Will be reported in validation
```

**Test**: Create rules, verify caches are built correctly.

- [ ] Done

### Step 3.4: Implement read methods
```python
def get_rule(self, glyph: str, side: str) -> str | None:
    """Get raw rule string for glyph/side."""
    return self._rules.get(glyph, {}).get(side)

def get_rules_for_glyph(self, glyph: str) -> dict[str, str] | None:
    """Get all rules for glyph. Returns {"left": "=A", "right": "=A"} or None."""
    return self._rules.get(glyph)

def get_all_rules(self) -> dict[str, dict[str, str]]:
    """Get copy of all rules."""
    return {g: dict(sides) for g, sides in self._rules.items()}

def get_dependents(self, glyph: str) -> set[str]:
    """Get glyphs that depend on this glyph."""
    return self._dependents_cache.get(glyph, set()).copy()

def get_dependencies(self, glyph: str) -> set[str]:
    """Get glyphs this glyph depends on."""
    result = set()
    for side, parsed in self._parsed_cache.get(glyph, {}).items():
        if parsed.source_glyph:
            result.add(parsed.source_glyph)
    return result
```

**Test**: Various read operations with test data.

- [ ] Done

### Step 3.5: Implement modification methods
```python
def set_rule(self, glyph: str, side: str, rule: str) -> None:
    """Set a rule. Rebuilds caches and saves to font."""
    # Validate syntax first
    is_valid, error = self._parser.validate_syntax(rule)
    if not is_valid:
        raise ValueError(f"Invalid rule syntax: {error}")

    self._rules.setdefault(glyph, {})[side] = rule
    self._rebuild_caches()
    self._save_to_font()

def remove_rule(self, glyph: str, side: str) -> str | None:
    """Remove a rule. Returns old rule for undo."""
    old_rule = self._rules.get(glyph, {}).pop(side, None)
    if old_rule:
        # Clean up empty glyph entry
        if not self._rules.get(glyph):
            del self._rules[glyph]
        self._rebuild_caches()
        self._save_to_font()
    return old_rule

def clear_rules_for_glyph(self, glyph: str) -> dict[str, str] | None:
    """Remove all rules for glyph. Returns old rules for undo."""
    old_rules = self._rules.pop(glyph, None)
    if old_rules:
        self._rebuild_caches()
        self._save_to_font()
    return old_rules
```

**Test**: Set, remove, clear operations with verification.

- [ ] Done

### Step 3.6: Implement validation
```python
def validate(self) -> ValidationReport:
    """Validate all rules and return detailed report."""
    cycles = self._detect_cycles()
    missing = []
    parse_errors = []
    self_refs = []

    for glyph, sides in self._rules.items():
        for side, rule in sides.items():
            # Check parse errors
            is_valid, error = self._parser.validate_syntax(rule)
            if not is_valid:
                parse_errors.append(ParseError(glyph, side, rule, error))
                continue

            parsed = self._parsed_cache.get(glyph, {}).get(side)
            if not parsed:
                continue

            # Check self-reference
            if parsed.source_glyph == glyph and not parsed.is_symmetry:
                self_refs.append(SelfReferenceWarning(glyph, side, rule))

            # Check missing glyph
            if parsed.source_glyph and parsed.source_glyph not in self._font:
                missing.append(MissingGlyphWarning(
                    glyph, side, rule, parsed.source_glyph
                ))

    is_valid = len(cycles) == 0 and len(parse_errors) == 0
    return ValidationReport(
        is_valid=is_valid,
        cycles=cycles,
        missing_glyphs=missing,
        parse_errors=parse_errors,
        self_references=self_refs
    )

def _detect_cycles(self) -> list[CycleError]:
    """Detect dependency cycles using DFS."""
    ...
```

**Test**: Various validation scenarios (valid, cycles, missing glyphs).

- [ ] Done

### Step 3.7: Implement evaluation
```python
def evaluate(self, glyph: str, side: str) -> int | None:
    """
    Evaluate rule and return computed margin value.
    Returns None if no rule or evaluation fails.
    """
    parsed = self._parsed_cache.get(glyph, {}).get(side)
    if not parsed:
        return None

    # Get source value
    if parsed.is_symmetry:
        # =| means RSB = LSB of same glyph
        opposite = "left" if side == "right" else "right"
        source_value = self._get_margin(glyph, opposite)
    elif parsed.source_glyph:
        source_side = side if parsed.source_side == "same" else parsed.source_side
        source_value = self._get_margin(parsed.source_glyph, source_side)
    else:
        return None

    if source_value is None:
        return None

    # Apply operator
    if parsed.operator is None:
        return source_value
    elif parsed.operator == "+":
        return round(source_value + parsed.operand)
    elif parsed.operator == "-":
        return round(source_value - parsed.operand)
    elif parsed.operator == "*":
        return round(source_value * parsed.operand)
    elif parsed.operator == "/":
        return round(source_value / parsed.operand) if parsed.operand != 0 else None

    return None

def _get_margin(self, glyph: str, side: str) -> int | None:
    """Get margin value from font."""
    if glyph not in self._font:
        return None
    g = self._font[glyph]
    return g.leftMargin if side == "left" else g.rightMargin
```

**Test**: Evaluate various rules with mock font.

- [ ] Done

### Step 3.8: Implement cascade helpers
```python
def get_cascade_order(self, glyph: str) -> list[str]:
    """
    Get ordered list of glyphs to update when glyph changes.
    Uses topological sort to ensure correct order.
    """
    result = []
    visited = set()

    def visit(g: str):
        if g in visited:
            return
        visited.add(g)
        for dep in self.get_dependents(g):
            visit(dep)
        result.append(g)

    for dep in self.get_dependents(glyph):
        visit(dep)

    # Remove the source glyph itself, reverse for correct order
    return [g for g in reversed(result) if g != glyph]
```

**Test**: Cascade order with chain dependencies.

- [ ] Done

### Checkpoint 3
- [ ] Manager loads/saves to font.lib correctly
- [ ] Caches built and maintained properly
- [ ] All read methods work
- [ ] All modification methods work
- [ ] Validation detects all error types
- [ ] Evaluation computes correct values
- [ ] Cascade order is correct

---

## Phase 4: Rule Commands

**Goal**: Create undoable commands for rule management.

### Step 4.1: Create SetMetricsRuleCommand
**File**: `src/ufo_spacing_lib/commands/rules.py`

```python
class SetMetricsRuleCommand(Command):
    """Set or update a metrics rule."""

    def __init__(self, glyph: str, side: str, rule: str):
        self.glyph = glyph
        self.side = side  # "left", "right", "both"
        self.rule = rule
        self._previous_rules: dict[int, dict[str, str] | None] = {}

    @property
    def description(self) -> str:
        return f"Set rule {self.glyph}.{self.side} = '{self.rule}'"

    def execute(self, context: FontContext,
                rules_managers: dict[int, MetricsRulesManager]) -> CommandResult:
        """Execute with rules managers for each font."""
        for font in context:
            manager = rules_managers[id(font)]
            self._previous_rules[id(font)] = manager.get_rules_for_glyph(self.glyph)

            if self.side == "both":
                manager.set_rule(self.glyph, "left", self.rule)
                manager.set_rule(self.glyph, "right", self.rule)
            else:
                manager.set_rule(self.glyph, self.side, self.rule)

        return CommandResult.ok(f"Set rule for {self.glyph}")

    def undo(self, context: FontContext,
             rules_managers: dict[int, MetricsRulesManager]) -> CommandResult:
        """Restore previous rules."""
        for font in context:
            manager = rules_managers[id(font)]
            previous = self._previous_rules.get(id(font))

            # Clear current rules for glyph
            manager.clear_rules_for_glyph(self.glyph)

            # Restore previous if existed
            if previous:
                for side, rule in previous.items():
                    manager.set_rule(self.glyph, side, rule)

        return CommandResult.ok()
```

**Test**: Execute and undo with verification.

- [ ] Done

### Step 4.2: Create RemoveMetricsRuleCommand
```python
class RemoveMetricsRuleCommand(Command):
    """Remove a metrics rule."""

    def __init__(self, glyph: str, side: str):
        self.glyph = glyph
        self.side = side  # "left", "right", "both"
        self._previous_rules: dict[int, dict[str, str] | None] = {}

    @property
    def description(self) -> str:
        return f"Remove rule {self.glyph}.{self.side}"

    def execute(self, context: FontContext,
                rules_managers: dict[int, MetricsRulesManager]) -> CommandResult:
        for font in context:
            manager = rules_managers[id(font)]
            self._previous_rules[id(font)] = manager.get_rules_for_glyph(self.glyph)

            if self.side == "both":
                manager.remove_rule(self.glyph, "left")
                manager.remove_rule(self.glyph, "right")
            else:
                manager.remove_rule(self.glyph, self.side)

        return CommandResult.ok(f"Removed rule for {self.glyph}")

    def undo(self, context: FontContext,
             rules_managers: dict[int, MetricsRulesManager]) -> CommandResult:
        # Restore previous rules
        ...
```

**Test**: Execute and undo with verification.

- [ ] Done

### Checkpoint 4
- [ ] SetMetricsRuleCommand works with undo
- [ ] RemoveMetricsRuleCommand works with undo
- [ ] Commands work with multi-font context
- [ ] All command tests pass

---

## Phase 5: SpacingEditor Integration

**Goal**: Integrate rules managers into SpacingEditor with proper lifecycle.

### Step 5.1: Extend SpacingEditor initialization
**File**: `src/ufo_spacing_lib/editors/spacing.py`

```python
class SpacingEditor:
    def __init__(
        self,
        fonts,
        *,
        primary_font=None,
        scales: dict | None = None,
    ):
        # Normalize fonts input
        if not isinstance(fonts, list):
            fonts = [fonts]

        # Create internal context
        self._context = FontContext(
            fonts=fonts,
            primary_font=primary_font or fonts[0],
            scales=scales or {}
        )

        # Create rules manager for each font
        self._rules_managers: dict[int, MetricsRulesManager] = {
            id(f): MetricsRulesManager(f) for f in fonts
        }

        # Active fonts (None = all)
        self._active_fonts: list | None = None

        # History
        self._history: list[tuple[Command, FontContext]] = []
        self._redo_stack: list[tuple[Command, FontContext]] = []

        # Callbacks
        self.on_change = None
        self.on_undo = None
        self.on_redo = None
```

**Test**: Create editor with single and multi-font, verify managers created.

- [ ] Done

### Step 5.2: Add font access properties
```python
@property
def font(self):
    """Primary font (convenience for single-font case)."""
    return self._context.primary_font

@property
def fonts(self) -> list:
    """All fonts in the editor."""
    return self._context.fonts

@property
def active_fonts(self) -> list:
    """Fonts that commands will apply to."""
    if self._active_fonts is None:
        return self._context.fonts
    return self._active_fonts

def set_active_fonts(self, fonts=None):
    """Set which fonts commands apply to. None = all fonts."""
    self._active_fonts = fonts
```

**Test**: Verify active_fonts behavior.

- [ ] Done

### Step 5.3: Add rules manager access
```python
def get_rules_manager(self, font=None) -> MetricsRulesManager:
    """
    Get rules manager for font.
    If font is None, returns manager for primary font.
    """
    if font is None:
        font = self._context.primary_font
    return self._rules_managers[id(font)]
```

**Test**: Access managers for different fonts.

- [ ] Done

### Step 5.4: Update execute method
```python
def execute(self, command: Command, *, font=None, fonts=None) -> CommandResult:
    """
    Execute command.

    Args:
        command: Command to execute
        font: Single font override (optional)
        fonts: Multiple fonts override (optional)

    If neither font nor fonts specified, uses active_fonts.
    """
    # Determine target fonts
    if font is not None:
        target_fonts = [font]
    elif fonts is not None:
        target_fonts = fonts
    else:
        target_fonts = self.active_fonts

    # Create execution context
    exec_context = FontContext(
        fonts=target_fonts,
        primary_font=target_fonts[0],
        scales={f: self._context.get_scale(f) for f in target_fonts}
    )

    # Check if command needs rules managers
    if self._is_rules_command(command):
        result = command.execute(exec_context, self._rules_managers)
    else:
        result = command.execute(exec_context)

    if result.success:
        self._history.append((command, exec_context))
        self._redo_stack.clear()
        if self.on_change:
            self.on_change(command, result)

    return result

def _is_rules_command(self, command) -> bool:
    """Check if command requires rules managers."""
    return isinstance(command, (SetMetricsRuleCommand, RemoveMetricsRuleCommand))
```

**Test**: Execute commands with various font targets.

- [ ] Done

### Step 5.5: Update undo/redo for rules commands
```python
def undo(self) -> CommandResult | None:
    if not self._history:
        return None

    command, context = self._history.pop()

    if self._is_rules_command(command):
        result = command.undo(context, self._rules_managers)
    else:
        result = command.undo(context)

    self._redo_stack.append((command, context))

    if self.on_undo:
        self.on_undo(command, result)

    return result
```

**Test**: Undo/redo rules commands.

- [ ] Done

### Checkpoint 5
- [ ] SpacingEditor creates managers for all fonts
- [ ] active_fonts switching works
- [ ] execute() works with font/fonts override
- [ ] Rules commands execute correctly
- [ ] Undo/redo works for rules commands
- [ ] All SpacingEditor tests pass

---

## Phase 6: Margin Commands Integration

**Goal**: Add automatic rules application to margin commands.

### Step 6.1: Extend CommandResult with warnings
**File**: `src/ufo_spacing_lib/commands/base.py`

```python
@dataclass(frozen=True)
class CommandResult:
    success: bool
    message: str = ""
    data: Any | None = None
    warnings: tuple[str, ...] = ()  # NEW
    affected_glyphs: tuple[str, ...] = ()  # NEW

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @classmethod
    def ok(cls, message: str = "", data: Any = None,
           warnings: tuple[str, ...] = (),
           affected_glyphs: tuple[str, ...] = ()) -> CommandResult:
        return cls(success=True, message=message, data=data,
                   warnings=warnings, affected_glyphs=affected_glyphs)
```

**Test**: Create results with warnings, verify properties.

- [ ] Done

### Step 6.2: Add apply_rules parameter to margin commands
**File**: `src/ufo_spacing_lib/commands/margins.py`

```python
class SetMarginCommand(Command):
    def __init__(
        self,
        glyph_name: str,
        side: str,
        value: int,
        propagate_to_composites: bool = True,
        recursive_propagate: bool = False,
        apply_rules: bool = True,  # NEW
    ):
        ...
        self.apply_rules = apply_rules
        self._cascade_state: dict[int, dict[str, Any]] = {}  # NEW: for undo
```

**Test**: Create commands with apply_rules parameter.

- [ ] Done

### Step 6.3: Implement cascade application in execute
```python
def execute(self, context: FontContext,
            rules_manager: MetricsRulesManager | None = None) -> CommandResult:
    warnings = []
    affected = [self.glyph_name]

    # ... existing execute logic ...

    # Apply rules cascade
    if self.apply_rules and rules_manager:
        cascade_warnings, cascade_affected = self._apply_rules_cascade(
            context, rules_manager
        )
        warnings.extend(cascade_warnings)
        affected.extend(cascade_affected)

    return CommandResult.ok(
        message=f"Set {self.side} margin of {self.glyph_name}",
        warnings=tuple(warnings),
        affected_glyphs=tuple(affected)
    )

def _apply_rules_cascade(
    self,
    context: FontContext,
    rules_manager: MetricsRulesManager
) -> tuple[list[str], list[str]]:
    """Apply rules to all dependent glyphs."""
    warnings = []
    affected = []

    # Get ordered dependents
    cascade_glyphs = rules_manager.get_cascade_order(self.glyph_name)

    for font in context:
        font_id = id(font)
        self._cascade_state.setdefault(font_id, {})

        for glyph in cascade_glyphs:
            for side in ["left", "right"]:
                rule = rules_manager.get_rule(glyph, side)
                if not rule:
                    continue

                # Save current state for undo
                g = font[glyph]
                self._cascade_state[font_id][f"{glyph}.{side}"] = {
                    "margin": g.leftMargin if side == "left" else g.rightMargin,
                    "width": g.width
                }

                # Evaluate and apply
                try:
                    new_value = rules_manager.evaluate(glyph, side)
                    if new_value is not None:
                        if side == "left":
                            g.leftMargin = new_value
                        else:
                            g.rightMargin = new_value
                        affected.append(glyph)
                except Exception as e:
                    warnings.append(f"Rule for {glyph}.{side}: {e}")

    return warnings, affected
```

**Test**: Execute with rules, verify cascade applied.

- [ ] Done

### Step 6.4: Implement cascade undo
```python
def undo(self, context: FontContext,
         rules_manager: MetricsRulesManager | None = None) -> CommandResult:
    # ... existing undo logic ...

    # Undo cascade (in reverse order)
    for font in context:
        font_id = id(font)
        cascade = self._cascade_state.get(font_id, {})

        for key, state in cascade.items():
            glyph, side = key.rsplit(".", 1)
            g = font[glyph]
            if side == "left":
                g.leftMargin = state["margin"]
            else:
                g.rightMargin = state["margin"]

    return CommandResult.ok()
```

**Test**: Undo with cascade, verify restoration.

- [ ] Done

### Step 6.5: Update SpacingEditor.execute for margin commands
```python
def execute(self, command: Command, *, font=None, fonts=None) -> CommandResult:
    ...

    # Check if margin command with apply_rules
    if self._is_margin_command(command) and getattr(command, 'apply_rules', False):
        # Get rules manager for primary font of execution context
        manager = self._rules_managers.get(id(exec_context.primary_font))
        result = command.execute(exec_context, rules_manager=manager)
    elif self._is_rules_command(command):
        result = command.execute(exec_context, self._rules_managers)
    else:
        result = command.execute(exec_context)

    ...

def _is_margin_command(self, command) -> bool:
    return isinstance(command, (SetMarginCommand, AdjustMarginCommand))
```

**Test**: Full integration test with editor.

- [ ] Done

### Step 6.6: Same changes for AdjustMarginCommand
Apply same pattern to `AdjustMarginCommand`.

- [ ] Done

### Checkpoint 6
- [ ] CommandResult supports warnings and affected_glyphs
- [ ] Margin commands have apply_rules parameter
- [ ] Cascade applies correctly
- [ ] Cascade undo works correctly
- [ ] SpacingEditor passes rules_manager to margin commands
- [ ] Full integration test passes

---

## Phase 7: Final Testing and Documentation

### Step 7.1: Integration tests
**File**: `tests/test_metrics_rules_integration.py`

```python
class TestMetricsRulesIntegration:
    def test_full_workflow(self):
        """Test complete workflow: setup rules, change margin, verify cascade."""
        ...

    def test_multi_font_rules(self):
        """Test rules with multiple fonts, each with own rules."""
        ...

    def test_undo_redo_cascade(self):
        """Test undo/redo preserves cascade changes."""
        ...

    def test_validation_from_host(self):
        """Test explicit validation call from host."""
        ...

    def test_runtime_rule_modification(self):
        """Test modifying rules without recreating editor."""
        ...

    def test_missing_glyph_warning(self):
        """Test warning when rule references missing glyph."""
        ...

    def test_cycle_detection(self):
        """Test cycle detection in validation."""
        ...
```

- [ ] Done

### Step 7.2: Update package exports
**File**: `src/ufo_spacing_lib/__init__.py`

Add exports:
- `MetricsRulesManager`
- `ValidationReport`
- `SetMetricsRuleCommand`
- `RemoveMetricsRuleCommand`
- Updated `CommandResult`

- [ ] Done

### Step 7.3: Update CLAUDE.md
Add documentation about metrics rules system.

- [ ] Done

### Checkpoint 7 (Final)
- [ ] All integration tests pass
- [ ] All unit tests pass
- [ ] Package exports updated
- [ ] Documentation updated
- [ ] `uv run pytest` passes
- [ ] `uv run mypy src/` passes
- [ ] `uv run ruff check src/ tests/` passes

---

## File Summary

New files to create:
1. `src/ufo_spacing_lib/rules_constants.py` - Constants
2. `src/ufo_spacing_lib/rules_core.py` - Data classes
3. `src/ufo_spacing_lib/rules_parser.py` - Rule parser
4. `src/ufo_spacing_lib/rules_manager.py` - Main manager
5. `src/ufo_spacing_lib/commands/rules.py` - Rule commands
6. `tests/test_rules_parser.py` - Parser tests
7. `tests/test_rules_manager.py` - Manager tests
8. `tests/test_rules_commands.py` - Command tests
9. `tests/test_metrics_rules_integration.py` - Integration tests

Files to modify:
1. `src/ufo_spacing_lib/commands/base.py` - Add warnings to CommandResult
2. `src/ufo_spacing_lib/commands/margins.py` - Add apply_rules and cascade
3. `src/ufo_spacing_lib/editors/spacing.py` - Add rules manager integration
4. `src/ufo_spacing_lib/__init__.py` - Add exports
5. `CLAUDE.md` - Update documentation
