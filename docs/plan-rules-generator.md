# Plan: Generate Rules from Composites

## Overview

Create a service function that analyzes composite glyphs and generates metrics rules based on component structure. Returns raw data for user review.

## Data Structures

### Input
- Font object with composite glyphs

### Output
```python
@dataclass
class RuleWarning:
    glyph: str
    code: str           # "W1"-"W7"
    message: str
    details: dict

@dataclass
class RuleGenerationResult:
    rules: dict[str, dict[str, str]]  # {"Aacute": {"left": "=A", "right": "=A"}}
    warnings: list[RuleWarning]
    skipped: list[str]  # glyphs skipped (no components, etc.)
```

### Warning Codes
| Code | Description |
|------|-------------|
| W1 | Component 1+ wider than component 0 |
| W2 | Component 1+ extends left of component 0 |
| W3 | Component 1+ extends right of component 0 |
| W4 | Component 0 has zero width |
| W5 | Component 0 does not exist in font |
| W6 | Glyph has mixed contours + components |
| W7 | Single component (informational) |

---

## Implementation Steps

### Phase 1: Data Classes
- [x] **1.1** Create `RuleWarning` dataclass in `rules_generator.py`
- [x] **1.2** Create `RuleGenerationResult` dataclass
- [x] **1.3** Add warning code constants (W1-W7)
- [x] **1.4** Write unit tests for data classes

### Phase 2: Core Analysis Functions
- [x] **2.1** Create `_get_component_bounds()` helper
  - Input: font, component
  - Output: (left, right, width) or None
  - Handles missing base glyphs
- [x] **2.2** Create `_analyze_glyph()` helper
  - Input: font, glyph
  - Output: (rule_dict, warnings_list) or None if skipped
- [x] **2.3** Create `_has_own_contours()` helper
  - Detects glyphs with both contours and components
- [x] **2.4** Write unit tests for helpers

### Phase 3: Main Function
- [x] **3.1** Create `generate_rules_from_composites()` function
  - Signature: `(font, glyph_names: list[str] | None = None) -> RuleGenerationResult`
  - If glyph_names is None, process all glyphs
- [x] **3.2** Implement iteration over glyphs
- [x] **3.3** Implement warning generation for each case (W1-W7)
- [x] **3.4** Write integration tests

### Phase 4: Edge Cases & Polish
- [x] **4.1** Handle nested composites (component 0 is itself a composite)
- [x] **4.2** Handle glyphs with existing rules (option to skip/overwrite)
- [x] **4.3** Add `include_single_component` parameter (default True)
- [x] **4.4** Write tests for edge cases

### Phase 5: Integration
- [x] **5.1** Export from `__init__.py`
- [x] **5.2** Test on real font (ClassicismBook)
- [ ] **5.3** Update documentation

---

## Progress Log

### Started: 2026-01-12

#### Checkpoint 1: Data Classes
- Status: COMPLETED
- Files: `src/ufo_spacing_lib/rules_generator.py`
- Tests: `tests/test_rules_generator.py`

#### Checkpoint 2: Core Analysis
- Status: COMPLETED
- `_get_component_bounds()` - extracts bounds with transformation
- `_has_own_contours()` - detects mixed composites
- `_analyze_glyph()` - generates rule + warnings for single glyph

#### Checkpoint 3: Main Function
- Status: COMPLETED
- `generate_rules_from_composites()` implemented with all parameters

#### Checkpoint 4: Edge Cases
- Status: COMPLETED
- Handles missing base glyphs
- Handles zero-width bases
- Handles mixed contours + components
- Handles single component glyphs

#### Checkpoint 5: Integration
- Status: COMPLETED
- Exported from `__init__.py`
- Tested on ClassicismBook-TextRegular.ufo (696 rules, 408 warnings)

---

## Test Cases

### Unit Tests
1. `RuleWarning` creation and attributes
2. `RuleGenerationResult` creation
3. `_get_component_bounds()` with valid/invalid components
4. `_analyze_glyph()` with various composite types

### Integration Tests
1. Simple composite (Aacute = A + acutecomb)
2. Multi-component (fi = f + i)
3. Single component (.sc variants)
4. Mixed contours + components
5. Missing base glyph
6. Zero-width base
7. Component extends beyond base

### Real Font Test
- ClassicismBook: 696 composites, verify warning counts match analysis script

---

## API Example

```python
from ufo_spacing_lib import generate_rules_from_composites

# Generate rules for all composites
result = generate_rules_from_composites(font)

# Or specific glyphs
result = generate_rules_from_composites(font, ["Aacute", "Agrave"])

# Access results
for glyph, sides in result.rules.items():
    print(f"{glyph}: left={sides['left']}, right={sides['right']}")

# Check warnings
for warning in result.warnings:
    print(f"[{warning.code}] {warning.glyph}: {warning.message}")
```
