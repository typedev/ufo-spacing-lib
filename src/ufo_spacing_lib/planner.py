"""
Margin Planner.

A pure planner for margin edits: given an edit, it returns every change the
edit implies, without touching the font. `apply_plan` then applies it.

The model is a cascade of shift events. A shift event means "the contents of
glyph X moved horizontally by s" (a left-margin change) or "X's advance width
changed by w" (a right-margin change).

1. **Structural compensation** (always on). When the contents of X shift by
   ``s``, every composite that uses X as a component gets the opposite offset
   on that component, so the composite stays pixel-for-pixel where it was.
   The correction is transform-aware: a component draws its base through the
   linear part of its transformation, so a base moving by ``(s, 0)`` moves by
   ``(xx*s, xy*s)`` inside the composite. A mirrored component (``xx = -1``)
   gets ``+s``. Compensation does not recurse: a composite held in place did
   not move, so composites built on it need nothing.

2. **Rules.** After compensation, metrics rules cascade from the edited glyph
   in dependency order. A rule on the left side shifts the whole contents of
   its glyph (contours, components, anchors, guidelines) and the advance by
   the same amount, exactly like the fontParts ``leftMargin`` setter. That
   shift is itself a shift event, so step 1 runs for the composites built on
   it. A rule on the right side changes the advance only.

Compensation never changes a glyph's drawing, so it never changes a margin.
That is why margins along the cascade are computed exactly as "margin read
from the source before the plan + the plan's deltas", with any margin reader
(upright or angled): a translation changes both by the same amount.

The planner reads glyphs only through ``name in source`` and
``source[name]``, so it works on a fontParts or defcon font or layer. It never
reads or writes ``font.lib``.

Example:
    >>> plan = plan_margin_edit(layer, "A", "left", delta=10, rules=rules)
    >>> snapshot(layer, plan.names)        # caller's own undo
    >>> apply_plan(layer, plan)
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, NamedTuple

from .rules_constants import SIDE_LEFT, SIDE_RIGHT
from .rules_core import (
    ParsedRule,
    RuleIssue,
    create_cycle_error,
    create_empty_glyph_warning,
    create_evaluation_failed_warning,
    create_missing_glyph_warning,
    create_rule_overridden_warning,
)
from .rules_manager import MetricsRulesManager

#: Reads a glyph's margin: ``(glyph, side) -> float | None``.
MarginReader = Callable[[Any, str], "float | None"]

#: Differences below this are treated as no change.
EPSILON = 1e-9

REASON_EDIT = "edit"

_SIDES = (SIDE_LEFT, SIDE_RIGHT)


# =============================================================================
# Plan data
# =============================================================================


@dataclass
class GlyphChange:
    """
    Everything a plan does to one glyph.

    All changes to one glyph are merged into a single GlyphChange. That is
    exact: every operation is a translation or a width change, and those
    commute. Apply order inside `apply_plan` is component offsets, then the
    contents shift, then the width.

    Attributes:
        name: Glyph name.
        shift: Horizontal shift of the whole contents (contours, components,
            anchors, guidelines). Comes from left-side edits and rules.
        width_delta: Total change of the advance width, *including* the
            shift. A left edit of +d is ``shift=d, width_delta=d``; a right
            edit of +d is ``shift=0, width_delta=d``.
        component_offsets: ``{component_index: (ddx, ddy)}`` added to
            component offsets, from compensation.
        reasons: Why the glyph is in the plan, in order: ``"edit"``,
            ``"compensate:<base>"``, ``"rule:<side> <rule text>"``.
    """

    name: str
    shift: float = 0.0
    width_delta: float = 0.0
    component_offsets: dict[int, tuple[float, float]] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    @property
    def left_delta(self) -> float:
        """Change of the left margin (any margin kind)."""
        return self.shift

    @property
    def right_delta(self) -> float:
        """Change of the right margin (any margin kind)."""
        return self.width_delta - self.shift

    @property
    def is_noop(self) -> bool:
        """True when applying this change would change nothing."""
        return (
            abs(self.shift) < EPSILON
            and abs(self.width_delta) < EPSILON
            and all(
                abs(dx) < EPSILON and abs(dy) < EPSILON
                for dx, dy in self.component_offsets.values()
            )
        )

    def inverted(self) -> GlyphChange:
        """The change that undoes this one."""
        return GlyphChange(
            name=self.name,
            shift=-self.shift,
            width_delta=-self.width_delta,
            component_offsets={
                index: (-dx, -dy) for index, (dx, dy) in self.component_offsets.items()
            },
            reasons=list(self.reasons),
        )


@dataclass
class Plan:
    """
    Result of planning a margin edit or a sync.

    Attributes:
        changes: One GlyphChange per touched glyph, in first-touch order.
            For an edit, the edited glyph comes first.
        issues: Rule issues met while planning (cycles, missing or empty
            glyphs, an edit overriding a rule, ...). Planning never raises
            for these.
        breaks: ``(glyph, side)`` rule sides this edit breaks: a direct
            edit on a side governed by an active rule (each also has a W10
            issue). The planner never records them; the caller marks them
            with `MetricsRulesManager.mark_broken` after applying the plan.
    """

    changes: list[GlyphChange] = field(default_factory=list)
    issues: list[RuleIssue] = field(default_factory=list)
    breaks: list[tuple[str, str]] = field(default_factory=list)

    @property
    def names(self) -> set[str]:
        """Every glyph the plan touches (snapshot these before applying)."""
        return {change.name for change in self.changes}

    @property
    def ordered_names(self) -> list[str]:
        """Touched glyph names in plan order."""
        return [change.name for change in self.changes]

    def get(self, name: str) -> GlyphChange | None:
        """The change for a glyph, or None if the plan does not touch it."""
        for change in self.changes:
            if change.name == name:
                return change
        return None

    def inverted(self) -> Plan:
        """A plan that undoes this one when applied after it (breaks nothing)."""
        return Plan(
            changes=[change.inverted() for change in reversed(self.changes)],
            issues=list(self.issues),
        )

    def __len__(self) -> int:
        return len(self.changes)

    def __bool__(self) -> bool:
        return bool(self.changes)

    def __iter__(self):
        return iter(self.changes)


class OutOfSync(NamedTuple):
    """A glyph side whose margin does not match its rule."""

    glyph: str
    side: str
    rule: str
    expected: float
    actual: float


class BrokenRule(NamedTuple):
    """
    A broken (dormant) rule side.

    `expected` is what the rule would give now (None if it cannot be
    evaluated); `actual` is the current margin (None without outline).
    """

    glyph: str
    side: str
    rule: str
    expected: float | None
    actual: float | None


@dataclass
class RulesStatus:
    """
    Result of `check_rules`.

    Attributes:
        out_of_sync: Active rule sides whose margin differs from their rule.
        broken: Broken rule sides, whether or not they hold. Never in
            `out_of_sync`.
        issues: Validation issues (cycles, parse errors, missing glyphs)
            plus evaluation issues (empty glyphs, division by zero).
    """

    out_of_sync: list[OutOfSync] = field(default_factory=list)
    broken: list[BrokenRule] = field(default_factory=list)
    issues: list[RuleIssue] = field(default_factory=list)

    @property
    def is_in_sync(self) -> bool:
        """True when every checked rule holds."""
        return not self.out_of_sync

    def for_glyph(self, glyph: str) -> list[OutOfSync]:
        """Out-of-sync entries for one glyph."""
        return [entry for entry in self.out_of_sync if entry.glyph == glyph]

    def issues_for_glyph(self, glyph: str) -> list[RuleIssue]:
        """Issues for one glyph."""
        return [issue for issue in self.issues if issue.glyph == glyph]


# =============================================================================
# Helpers
# =============================================================================


def upright_margins(glyph: Any, side: str) -> float | None:
    """Default margin reader: ``glyph.leftMargin`` / ``glyph.rightMargin``."""
    if side == SIDE_LEFT:
        value: float | None = glyph.leftMargin
    else:
        value = glyph.rightMargin
    return value


def angled_margins(source: Any, italic_angle: float | None) -> MarginReader:
    """
    Build a margin reader that measures along the italic angle.

    Components are resolved through `source`. For an upright angle this
    returns `upright_margins`. Needs fontTools.

    Args:
        source: Glyph source used to draw components.
        italic_angle: The font's italicAngle in degrees (negative leans right).
    """
    if not italic_angle:
        return upright_margins

    import math

    from fontTools.misc.transform import Transform
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.transformPen import TransformPen

    unskew = Transform(1, 0, math.tan(math.radians(italic_angle)), 1, 0, 0)

    def read(glyph: Any, side: str) -> float | None:
        pen = BoundsPen(source)
        glyph.draw(TransformPen(pen, unskew))
        if pen.bounds is None:
            return None
        x_min, _, x_max, _ = pen.bounds
        return float(x_min) if side == SIDE_LEFT else float(glyph.width - x_max)

    return read


def component_shift(
    transformation: tuple[float, ...], delta: tuple[float, float]
) -> tuple[float, float]:
    """
    How far a component's drawing travels when its base moves by `delta`.

    The transformation is ``(xx, xy, yx, yy, dx, dy)``, read as
    ``x' = xx*x + yx*y + dx`` and ``y' = xy*x + yy*y + dy``, so a base
    moved by ``delta`` arrives moved by the linear part applied to it.
    """
    xx, xy, yx, yy = transformation[:4]
    dx, dy = delta
    return (xx * dx + yx * dy, xy * dx + yy * dy)


def _iter_names(source: Any) -> list[str]:
    """Glyph names of a source (fontParts/defcon font or layer, or a mapping)."""
    keys = getattr(source, "keys", None)
    if callable(keys):
        return list(keys())
    names = []
    for item in source:
        names.append(item if isinstance(item, str) else item.name)
    return names


def build_reverse_component_map(source: Any) -> dict[str, list[str]]:
    """
    Build ``{base: [composites]}`` for a glyph source.

    Uses ``getReverseComponentMapping()`` when the source has it (fontParts
    fonts and layers, defcon), otherwise scans every glyph. Building it is
    expensive, so cache it and pass it as `reverse_map`.
    """
    getter = getattr(source, "getReverseComponentMapping", None)
    if callable(getter):
        try:
            mapping = getter()
        except Exception:
            mapping = None
        if mapping is not None:
            return {base: sorted(hosts) for base, hosts in mapping.items()}

    result: dict[str, set[str]] = {}
    for name in _iter_names(source):
        for component in getattr(source[name], "components", None) or ():
            result.setdefault(component.baseGlyph, set()).add(name)
    return {base: sorted(hosts) for base, hosts in result.items()}


def _as_manager(rules: Any, source: Any) -> MetricsRulesManager | None:
    if rules is None:
        return None
    if isinstance(rules, MetricsRulesManager):
        return rules
    return MetricsRulesManager.from_rules(rules, source)


def _check_side(side: str) -> None:
    if side not in _SIDES:
        raise ValueError(f"side must be 'left' or 'right', not {side!r}")


def _is_self_referencing(glyph: str, parsed: ParsedRule) -> bool:
    return parsed.is_symmetry or parsed.source_glyph == glyph


def _rule_source(glyph: str, side: str, parsed: ParsedRule) -> tuple[str, str]:
    """The (glyph, side) a rule reads."""
    name = glyph if parsed.is_symmetry else parsed.source_glyph
    assert name is not None
    return name, parsed.source_side_for(side)


def _ordered_components(
    nodes: set[str], manager: MetricsRulesManager
) -> list[list[str]]:
    """
    Strongly connected components of the rule graph restricted to `nodes`,
    dependencies first (Tarjan). Self-references are not edges.
    """
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    result: list[list[str]] = []
    counter = [0]

    def edges(node: str) -> list[str]:
        return sorted(
            dep for dep in manager.get_dependencies(node) if dep in nodes and dep != node
        )

    def strongconnect(root: str) -> None:
        # Iterative Tarjan: rule chains can be long.
        work = [(root, iter(edges(root)))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter[0]
                    counter[0] += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(edges(child))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                result.append(sorted(component))

    for node in sorted(nodes):
        if node not in index:
            strongconnect(node)
    return result


# =============================================================================
# Planner
# =============================================================================


class _Planner:
    """Accumulates a plan. Never mutates the source."""

    def __init__(
        self,
        source: Any,
        manager: MetricsRulesManager | None,
        reverse_map: dict[str, list[str]] | None,
        margins: MarginReader | None,
        round_values: bool,
    ):
        self.source = source
        self.manager = manager
        self._reverse_map = reverse_map
        self.read = margins or upright_margins
        self.round_values = round_values
        self.changes: dict[str, GlyphChange] = {}
        self.issues: list[RuleIssue] = []
        self.breaks: list[tuple[str, str]] = []
        self._original: dict[tuple[str, str], float | None] = {}

    # -- state ---------------------------------------------------------------

    @property
    def reverse_map(self) -> dict[str, list[str]]:
        if self._reverse_map is None:
            self._reverse_map = build_reverse_component_map(self.source)
        return self._reverse_map

    def exists(self, name: str) -> bool:
        try:
            return name in self.source
        except (TypeError, AttributeError):
            return False

    def change(self, name: str) -> GlyphChange:
        change = self.changes.get(name)
        if change is None:
            change = self.changes[name] = GlyphChange(name)
        return change

    def original_margin(self, name: str, side: str) -> float | None:
        key = (name, side)
        if key not in self._original:
            value = self.read(self.source[name], side) if self.exists(name) else None
            self._original[key] = None if value is None else float(value)
        return self._original[key]

    def margin(self, name: str, side: str) -> float | None:
        """Margin after the changes planned so far."""
        value = self.original_margin(name, side)
        if value is None:
            return None
        change = self.changes.get(name)
        if change is None:
            return value
        return value + (change.left_delta if side == SIDE_LEFT else change.right_delta)

    def side_changed(self, name: str, side: str) -> bool:
        change = self.changes.get(name)
        if change is None:
            return False
        delta = change.left_delta if side == SIDE_LEFT else change.right_delta
        return abs(delta) >= EPSILON

    # -- events --------------------------------------------------------------

    def shift(self, name: str, amount: float, reason: str) -> None:
        """Shift the contents of `name` (and its advance) by `amount`."""
        change = self.change(name)
        change.shift += amount
        change.width_delta += amount
        change.reasons.append(reason)
        self.compensate(name, amount)

    def widen(self, name: str, amount: float, reason: str) -> None:
        """Change the advance of `name` by `amount`."""
        change = self.change(name)
        change.width_delta += amount
        change.reasons.append(reason)

    def compensate(self, base: str, amount: float) -> None:
        """Hold every composite built on `base` in place after it moved."""
        if abs(amount) < EPSILON:
            return
        for host_name in self.reverse_map.get(base, ()):
            if host_name == base or not self.exists(host_name):
                continue
            host = self.source[host_name]
            offsets: dict[int, tuple[float, float]] = {}
            for i, component in enumerate(getattr(host, "components", None) or ()):
                if component.baseGlyph != base:
                    continue
                sx, sy = component_shift(component.transformation, (amount, 0.0))
                if abs(sx) < EPSILON and abs(sy) < EPSILON:
                    continue  # a collapsed component has nowhere to go
                offsets[i] = (-sx, -sy)
            if not offsets:
                continue
            change = self.change(host_name)
            for i, (dx, dy) in offsets.items():
                old_dx, old_dy = change.component_offsets.get(i, (0.0, 0.0))
                change.component_offsets[i] = (old_dx + dx, old_dy + dy)
            change.reasons.append(f"compensate:{base}")

    # -- rules ---------------------------------------------------------------

    def evaluate(self, glyph: str, side: str) -> float | None:
        """Target margin of a rule under the current plan, or None + issue."""
        assert self.manager is not None
        parsed = self.manager.get_parsed_rule(glyph, side)
        rule = self.manager.get_rule(glyph, side) or ""
        if parsed is None:
            return None
        source_name, source_side = _rule_source(glyph, side, parsed)
        if not self.exists(source_name):
            self.issues.append(
                create_missing_glyph_warning(glyph, side, rule, source_name)
            )
            return None
        source_value = self.margin(source_name, source_side)
        if source_value is None:
            self.issues.append(
                create_empty_glyph_warning(glyph, side, rule, source_name, "source")
            )
            return None
        value = parsed.apply(source_value)
        if value is None:
            self.issues.append(
                create_evaluation_failed_warning(glyph, side, rule, "division by zero")
            )
            return None
        if self.round_values:
            value = float(round(value))
        return value

    def apply_rule(self, glyph: str, side: str) -> None:
        assert self.manager is not None
        rule = self.manager.get_rule(glyph, side) or ""
        if not self.exists(glyph):
            return
        target = self.evaluate(glyph, side)
        if target is None:
            return
        current = self.margin(glyph, side)
        if current is None:
            self.issues.append(
                create_empty_glyph_warning(glyph, side, rule, glyph, "target")
            )
            return
        delta = target - current
        if abs(delta) < EPSILON:
            return
        reason = f"rule:{side} {rule}"
        if side == SIDE_LEFT:
            self.shift(glyph, delta, reason)
        else:
            self.widen(glyph, delta, reason)

    def rule_sides(self, glyph: str) -> list[tuple[str, ParsedRule]]:
        """A glyph's parsed rules, self-referencing sides last."""
        assert self.manager is not None
        sides = []
        for side in _SIDES:
            parsed = self.manager.get_parsed_rule(glyph, side)
            if parsed is not None:
                sides.append((side, parsed))
        sides.sort(key=lambda item: _is_self_referencing(glyph, item[1]))
        return sides

    def cascade(
        self,
        nodes: set[str],
        forced: set[tuple[str, str]],
        skip: set[tuple[str, str]],
    ) -> None:
        """
        Run the rules of `nodes` in dependency order.

        A rule side runs when it is in `forced` or when the margin it reads
        has changed in this plan. Broken sides never run unless forced.
        Glyphs caught in a cycle are skipped with one E02 issue per cycle.
        """
        assert self.manager is not None
        for component in _ordered_components(nodes, self.manager):
            if len(component) > 1:
                self.issues.append(create_cycle_error(component + [component[0]]))
                continue
            glyph = component[0]
            for side, parsed in self.rule_sides(glyph):
                if (glyph, side) in skip:
                    continue
                if (glyph, side) in forced:
                    self.apply_rule(glyph, side)
                elif self.manager.is_broken(glyph, side):
                    continue
                elif self.side_changed(*_rule_source(glyph, side, parsed)):
                    self.apply_rule(glyph, side)

    def plan(self) -> Plan:
        changes = [c for c in self.changes.values() if not c.is_noop]
        return Plan(changes=changes, issues=self.issues, breaks=self.breaks)


# =============================================================================
# Public API
# =============================================================================


def plan_margin_edit(
    source: Any,
    glyph_name: str,
    side: str,
    delta: float | None = None,
    value: float | None = None,
    *,
    rules: dict | MetricsRulesManager | None = None,
    reverse_map: dict[str, list[str]] | None = None,
    margins: MarginReader | None = None,
    round_values: bool = False,
) -> Plan:
    """
    Plan a margin edit and everything it implies. Does not mutate.

    Args:
        source: Glyph source (fontParts/defcon font or layer).
        glyph_name: Glyph to edit.
        side: "left" or "right".
        delta: Change of the margin. Exactly one of delta/value.
        value: Target margin, measured by `margins`.
        rules: Rules dict ({glyph: {side: rule}} or the lib value), a
            MetricsRulesManager, or None for compensation only.
        reverse_map: Cached ``{base: [composites]}``; built when None.
        margins: Margin reader ``(glyph, side) -> float | None``. Default
            reads upright ``leftMargin`` / ``rightMargin``.
        round_values: Round rule results to integers. Off by default, so a
            cascade does not accumulate rounding.

    Returns:
        Plan with the edited glyph first.

    Raises:
        ValueError: Bad side, or not exactly one of delta/value.
        KeyError: The glyph is not in the source.

    Notes:
        - The edited glyph is not re-ruled: the edit wins over its own rule
          on the edited side. If that rule is active, the plan carries a
          W10 issue and lists the side in `plan.breaks`; an already broken
          side gives neither. Its other side is re-evaluated only when that
          rule reads the glyph itself (``=|``). Its dependents cascade as
          usual and read its new margin.
        - Broken rule sides are never evaluated.
        - A glyph without outline has no margin: a delta edit changes its
          width only, a value edit gives a W11 issue and no change.
    """
    _check_side(side)
    if (delta is None) == (value is None):
        raise ValueError("pass exactly one of delta or value")
    if glyph_name not in source:
        raise KeyError(glyph_name)

    manager = _as_manager(rules, source)
    planner = _Planner(source, manager, reverse_map, margins, round_values)

    current = planner.original_margin(glyph_name, side)
    if current is None:
        if delta is not None:
            planner.widen(glyph_name, delta, REASON_EDIT)
        else:
            planner.issues.append(
                create_empty_glyph_warning(glyph_name, side, None, glyph_name, "target")
            )
        return planner.plan()

    amount = delta if delta is not None else value - current  # type: ignore[operator]
    if abs(amount) < EPSILON:
        return planner.plan()
    if side == SIDE_LEFT:
        planner.shift(glyph_name, amount, REASON_EDIT)
    else:
        planner.widen(glyph_name, amount, REASON_EDIT)

    if manager is None:
        return planner.plan()

    own_rule = manager.get_rule(glyph_name, side)
    if (
        own_rule is not None
        and manager.get_parsed_rule(glyph_name, side) is not None
        and not manager.is_broken(glyph_name, side)
    ):
        planner.breaks.append((glyph_name, side))
        planner.issues.append(
            create_rule_overridden_warning(
                glyph_name,
                side,
                own_rule,
                planner.evaluate(glyph_name, side),
                current + amount,
            )
        )

    nodes = manager.get_affected_glyphs(glyph_name)
    nodes.add(glyph_name)
    planner.cascade(nodes, forced=set(), skip={(glyph_name, side)})
    return planner.plan()


def plan_restore(
    source: Any,
    rules: dict | MetricsRulesManager,
    glyph_name: str,
    side: str,
    *,
    reverse_map: dict[str, list[str]] | None = None,
    margins: MarginReader | None = None,
    round_values: bool = False,
) -> Plan:
    """
    Plan bringing one rule side back in line, e.g. after restoring it.

    Only that side is re-ruled (unlike ``plan_sync(names=[glyph])``, which
    would also sync the glyph's other side); its dependents cascade. The
    side is evaluated even if it is still marked broken, so the caller may
    call `MetricsRulesManager.restore_rule` before or after planning.

    Args:
        source: Glyph source.
        rules: Rules dict or MetricsRulesManager.
        glyph_name: Glyph whose rule to restore.
        side: "left", "right", or "both".
        reverse_map: Cached ``{base: [composites]}``.
        margins: Margin reader.
        round_values: Round rule results to integers.
    """
    if side != "both":
        _check_side(side)
    manager = _as_manager(rules, source)
    assert manager is not None
    planner = _Planner(source, manager, reverse_map, margins, round_values)
    sides = _SIDES if side == "both" else (side,)
    forced = {(glyph_name, one) for one in sides if manager.has_rule(glyph_name, one)}
    if forced:
        nodes = manager.get_affected_glyphs(glyph_name) | {glyph_name}
        planner.cascade(nodes, forced=forced, skip=set())
    return planner.plan()


def plan_sync(
    source: Any,
    rules: dict | MetricsRulesManager,
    names: Iterable[str] | None = None,
    *,
    reverse_map: dict[str, list[str]] | None = None,
    margins: MarginReader | None = None,
    round_values: bool = False,
) -> Plan:
    """
    Plan bringing ruled glyphs in line with their rules. Does not mutate.

    Args:
        source: Glyph source.
        rules: Rules dict or MetricsRulesManager.
        names: Ruled glyphs to sync (targets). None means every ruled
            glyph. Glyphs downstream of a synced glyph are re-evaluated
            too, even outside `names`, when what they read has changed.
        reverse_map: Cached ``{base: [composites]}``.
        margins: Margin reader.
        round_values: Round rule results to integers.

    Returns:
        Plan in dependency order. Broken rule sides are left alone; restore
        them with `plan_restore`.
    """
    manager = _as_manager(rules, source)
    assert manager is not None
    planner = _Planner(source, manager, reverse_map, margins, round_values)

    ruled = set(manager.get_all_rules())
    targets = ruled if names is None else ruled & set(names)
    nodes = set(targets)
    for name in targets:
        nodes |= manager.get_affected_glyphs(name)
    forced = {
        (glyph, side)
        for glyph in targets
        for side in _SIDES
        if manager.has_rule(glyph, side) and not manager.is_broken(glyph, side)
    }
    planner.cascade(nodes, forced=forced, skip=set())
    return planner.plan()


def check_rules(
    source: Any,
    rules: dict | MetricsRulesManager,
    names: Iterable[str] | None = None,
    *,
    margins: MarginReader | None = None,
    round_values: bool = False,
    tolerance: float = 1e-6,
) -> RulesStatus:
    """
    Report ruled glyphs whose margins do not match their rules.

    Args:
        source: Glyph source.
        rules: Rules dict or MetricsRulesManager.
        names: Ruled glyphs to check. None means every ruled glyph.
        margins: Margin reader.
        round_values: Compare against rounded rule results.
        tolerance: Largest difference still counted as in sync.

    Returns:
        RulesStatus with out-of-sync entries, broken sides (with what
        the rule would give now) and issues. Validation issues
        (cycles, parse errors, missing glyphs) are included for the whole
        rule set when `names` is None, else for the checked glyphs.
    """
    manager = _as_manager(rules, source)
    assert manager is not None
    planner = _Planner(source, manager, None, margins, round_values)
    targets = set(manager.get_all_rules()) if names is None else set(names)

    status = RulesStatus()
    report = manager.validate()
    for issue in report.issues:
        cycle = issue.details.get("cycle")
        if names is None or issue.glyph in targets or (cycle and targets & set(cycle)):
            status.issues.append(issue)
    reported = {(i.glyph, i.details.get("side"), i.code) for i in status.issues}

    for glyph in sorted(targets):
        if not planner.exists(glyph):
            continue
        for side in _SIDES:
            rule = manager.get_rule(glyph, side)
            if rule is None or manager.get_parsed_rule(glyph, side) is None:
                continue
            expected = planner.evaluate(glyph, side)
            actual = planner.margin(glyph, side)
            if manager.is_broken(glyph, side):
                status.broken.append(BrokenRule(glyph, side, rule, expected, actual))
                continue
            if expected is None:
                continue
            if actual is None:
                planner.issues.append(
                    create_empty_glyph_warning(glyph, side, rule, glyph, "target")
                )
                continue
            if abs(expected - actual) > tolerance:
                status.out_of_sync.append(OutOfSync(glyph, side, rule, expected, actual))

    for issue in planner.issues:
        # Missing glyphs are already reported by validate().
        if (issue.glyph, issue.details.get("side"), issue.code) not in reported:
            status.issues.append(issue)
    return status


def apply_plan(source: Any, plan: Plan) -> list[str]:
    """
    Apply a plan to a glyph source.

    Per glyph: component offsets first, then the contents shift (contours,
    components, anchors, guidelines via ``glyph.moveBy`` for fontParts or
    ``glyph.move`` for defcon), then the width.

    Returns:
        Names of the glyphs changed, in plan order.
    """
    applied = []
    for change in plan.changes:
        if change.name not in source:
            continue
        glyph = source[change.name]
        components = list(getattr(glyph, "components", None) or ())
        for index, (dx, dy) in sorted(change.component_offsets.items()):
            if index < len(components):
                _move(components[index], dx, dy)
        if change.shift:
            _move(glyph, change.shift, 0.0)
        if change.width_delta:
            glyph.width = glyph.width + change.width_delta
        changed = getattr(glyph, "changed", None)
        if callable(changed):
            changed()
        applied.append(change.name)
    return applied


def _move(obj: Any, dx: float, dy: float) -> None:
    """Translate a glyph or component (fontParts moveBy / defcon move)."""
    mover = getattr(obj, "moveBy", None)
    if mover is None:
        mover = getattr(obj, "move", None)
    if mover is not None:
        mover((dx, dy))
        return
    x, y = obj.offset
    obj.offset = (x + dx, y + dy)
