#!/usr/bin/env python3
"""
Performance benchmark for metrics rules and composite propagation.

Tests different scenarios on a real font:
1. Pure propagation (no rules)
2. Rules cascade only
3. Mixed mode (rules + propagation)
4. Different chain lengths (depth 1, 2, 3)
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from defcon import Font

from ufo_spacing_lib.commands.margins import AdjustMarginCommand
from ufo_spacing_lib.commands.rules import SetMetricsRuleCommand, SyncRulesCommand
from ufo_spacing_lib.editors.spacing import SpacingEditor


def analyze_font_structure(font):
    """Analyze font to find composite chains."""
    # Build reverse component map
    reverse_map = {}
    for glyph in font:
        for comp in glyph.components:
            base = comp.baseGlyph
            if base not in reverse_map:
                reverse_map[base] = []
            reverse_map[base].append(glyph.name)

    # Calculate chain depths
    def get_depth(glyph_name, visited=None):
        if visited is None:
            visited = set()
        if glyph_name in visited:
            return 0
        visited.add(glyph_name)

        if glyph_name not in reverse_map:
            return 0

        max_child_depth = 0
        for child in reverse_map[glyph_name]:
            child_depth = get_depth(child, visited.copy())
            max_child_depth = max(max_child_depth, child_depth)

        return max_child_depth + 1

    # Find all base glyphs with their depths
    depths = {}
    for glyph_name in reverse_map:
        depth = get_depth(glyph_name)
        if depth not in depths:
            depths[depth] = []
        depths[depth].append(glyph_name)

    return reverse_map, depths


def count_descendants(glyph_name, reverse_map):
    """Count all descendants of a glyph."""
    count = 0
    to_visit = [glyph_name]
    visited = set()

    while to_visit:
        current = to_visit.pop()
        if current in visited:
            continue
        visited.add(current)

        if current in reverse_map:
            children = reverse_map[current]
            count += len(children)
            to_visit.extend(children)

    return count


def benchmark_scenario(editor, font, glyph_name, side, delta, iterations, scenario_name):
    """Run benchmark for a specific scenario."""
    times = []
    original_margin = getattr(font[glyph_name], f"{side}Margin")

    for i in range(iterations):
        # Reset to original
        setattr(font[glyph_name], f"{side}Margin", original_margin)
        editor.clear_history()

        # Time the operation
        cmd = AdjustMarginCommand(glyph_name, side, delta)
        start = time.perf_counter()
        result = editor.execute(cmd)
        end = time.perf_counter()

        times.append(end - start)

        # Undo to reset state
        editor.undo()

    # Reset final state
    setattr(font[glyph_name], f"{side}Margin", original_margin)

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)

    return {
        "scenario": scenario_name,
        "glyph": glyph_name,
        "avg_ms": avg_time * 1000,
        "min_ms": min_time * 1000,
        "max_ms": max_time * 1000,
        "iterations": iterations,
    }


def run_benchmarks(font_path, iterations=100):
    """Run all benchmarks on the font."""
    print(f"Loading font: {font_path}")
    font = Font(font_path)
    print(f"Font loaded: {len(font)} glyphs")

    # Analyze structure
    reverse_map, depths = analyze_font_structure(font)
    print(f"\nFont structure analysis:")
    print(f"  Total glyphs: {len(font)}")
    print(f"  Base glyphs with composites: {len(reverse_map)}")
    for depth in sorted(depths.keys(), reverse=True):
        count = len(depths[depth])
        print(f"  Depth {depth}: {count} glyphs")

    # Select test candidates
    test_candidates = []

    # Depth 3 (if available)
    if 3 in depths:
        for g in depths[3][:2]:
            desc = count_descendants(g, reverse_map)
            test_candidates.append((g, 3, desc))

    # Depth 2
    if 2 in depths:
        # Pick glyphs with varying descendant counts
        d2_glyphs = [(g, count_descendants(g, reverse_map)) for g in depths[2]]
        d2_glyphs.sort(key=lambda x: x[1], reverse=True)
        for g, desc in d2_glyphs[:3]:
            test_candidates.append((g, 2, desc))

    # Depth 1 (many composites)
    if 1 in depths:
        d1_glyphs = [(g, count_descendants(g, reverse_map)) for g in depths[1]]
        d1_glyphs.sort(key=lambda x: x[1], reverse=True)
        for g, desc in d1_glyphs[:2]:
            test_candidates.append((g, 1, desc))

    print(f"\nTest candidates:")
    for glyph, depth, desc in test_candidates:
        print(f"  {glyph}: depth={depth}, descendants={desc}")

    results = []

    # =========================================================================
    # Scenario 1: Pure propagation (no rules)
    # =========================================================================
    print("\n" + "=" * 60)
    print("SCENARIO 1: Pure propagation (no rules)")
    print("=" * 60)

    editor = SpacingEditor(font)

    for glyph_name, depth, desc_count in test_candidates:
        result = benchmark_scenario(
            editor, font, glyph_name, "left", 10, iterations,
            f"propagate_only_depth{depth}"
        )
        result["depth"] = depth
        result["descendants"] = desc_count
        results.append(result)
        print(f"  {glyph_name}: {result['avg_ms']:.3f} ms (depth={depth}, desc={desc_count})")

    # =========================================================================
    # Scenario 2: Rules cascade only (no composites involved)
    # =========================================================================
    print("\n" + "=" * 60)
    print("SCENARIO 2: Rules cascade only")
    print("=" * 60)

    # Create editor with rules
    editor = SpacingEditor(font)

    # Set up rules: dependent glyphs reference test glyph
    # Pick a simple glyph and create rules pointing to it
    test_glyph = "A"
    rule_targets = ["Aacute", "Agrave", "Abreve", "Acircumflex", "Adieresis"]

    # Filter to existing glyphs
    rule_targets = [g for g in rule_targets if g in font]

    if rule_targets:
        print(f"  Setting up rules: {len(rule_targets)} glyphs depend on {test_glyph}")

        for target in rule_targets:
            editor.execute(SetMetricsRuleCommand(target, "left", f"={test_glyph}"))

        # Benchmark
        result = benchmark_scenario(
            editor, font, test_glyph, "left", 10, iterations,
            "rules_cascade_only"
        )
        result["depth"] = 1
        result["descendants"] = len(rule_targets)
        results.append(result)
        print(f"  {test_glyph}: {result['avg_ms']:.3f} ms (rules={len(rule_targets)})")

        # Clean up rules
        editor.clear_history()

    # =========================================================================
    # Scenario 3: Rules with arithmetic (=A+10)
    # =========================================================================
    print("\n" + "=" * 60)
    print("SCENARIO 3: Rules with arithmetic (=A+10)")
    print("=" * 60)

    editor = SpacingEditor(font)

    if rule_targets:
        for target in rule_targets:
            editor.execute(SetMetricsRuleCommand(target, "left", f"={test_glyph}+10"))

        result = benchmark_scenario(
            editor, font, test_glyph, "left", 10, iterations,
            "rules_arithmetic"
        )
        result["depth"] = 1
        result["descendants"] = len(rule_targets)
        results.append(result)
        print(f"  {test_glyph}: {result['avg_ms']:.3f} ms (rules={len(rule_targets)})")

        editor.clear_history()

    # =========================================================================
    # Scenario 4: Mixed mode - rules + propagation
    # =========================================================================
    print("\n" + "=" * 60)
    print("SCENARIO 4: Mixed mode (rules + propagation)")
    print("=" * 60)

    # Find a glyph that has both composites and can have rules
    for glyph_name, depth, desc_count in test_candidates:
        if desc_count >= 3:
            editor = SpacingEditor(font)

            # Get composites
            composites = reverse_map.get(glyph_name, [])[:5]

            if len(composites) >= 2:
                # Set rule on half of them
                ruled = composites[:len(composites)//2]
                for comp in ruled:
                    # Rule pointing to a different glyph (H if exists)
                    if "H" in font:
                        editor.execute(SetMetricsRuleCommand(comp, "left", "=H"))

                result = benchmark_scenario(
                    editor, font, glyph_name, "left", 10, iterations,
                    f"mixed_mode_depth{depth}"
                )
                result["depth"] = depth
                result["descendants"] = desc_count
                result["ruled"] = len(ruled)
                result["propagated"] = len(composites) - len(ruled)
                results.append(result)
                print(f"  {glyph_name}: {result['avg_ms']:.3f} ms "
                      f"(depth={depth}, desc={desc_count}, ruled={len(ruled)})")
            break

    # =========================================================================
    # Scenario 5: Chain cascade (rules pointing to rules)
    # =========================================================================
    print("\n" + "=" * 60)
    print("SCENARIO 5: Chain cascade (A -> B -> C)")
    print("=" * 60)

    editor = SpacingEditor(font)

    # Build a chain: A -> Aacute -> some other glyph
    chain_start = "A"
    chain = []

    if "Aacute" in font and "Agrave" in font:
        chain = ["Aacute", "Agrave"]
        # Aacute depends on A, Agrave depends on Aacute
        editor.execute(SetMetricsRuleCommand("Aacute", "left", "=A"))
        editor.execute(SetMetricsRuleCommand("Agrave", "left", "=Aacute"))

        result = benchmark_scenario(
            editor, font, chain_start, "left", 10, iterations,
            "chain_cascade_depth2"
        )
        result["depth"] = 2
        result["descendants"] = 2
        results.append(result)
        print(f"  {chain_start}: {result['avg_ms']:.3f} ms (chain length=2)")

    # =========================================================================
    # Scenario 6: Deferred sync (multiple changes, single sync)
    # =========================================================================
    print("\n" + "=" * 60)
    print("SCENARIO 6: Deferred sync (batch mode)")
    print("=" * 60)

    editor = SpacingEditor(font)

    # Set up rules for multiple glyphs
    sync_sources = []
    sync_targets = []

    for base in ["A", "E", "O", "H", "N"]:
        if base not in font:
            continue
        # Find glyphs that could depend on this base
        candidates = [f"{base}acute", f"{base}grave", f"{base}circumflex",
                      f"{base}dieresis", f"{base}tilde"]
        targets = [g for g in candidates if g in font]

        if targets:
            sync_sources.append(base)
            sync_targets.extend(targets)
            for t in targets:
                editor.execute(SetMetricsRuleCommand(t, "left", f"={base}"))

    if sync_sources and sync_targets:
        print(f"  Setup: {len(sync_sources)} sources, {len(sync_targets)} dependent glyphs")

        # Benchmark: multiple changes with apply_rules=False, then single sync
        def benchmark_deferred_sync():
            times = []
            for _ in range(iterations):
                # Save original margins
                originals = {}
                for g in sync_sources + sync_targets:
                    if g in font:
                        originals[g] = font[g].leftMargin

                # Make multiple changes without cascade
                start = time.perf_counter()
                for source in sync_sources:
                    cmd = AdjustMarginCommand(source, "left", 5, apply_rules=False)
                    editor.execute(cmd)

                # Single sync operation
                sync_cmd = SyncRulesCommand(sync_sources)
                editor.execute(sync_cmd)
                end = time.perf_counter()

                times.append(end - start)

                # Restore
                for g, val in originals.items():
                    font[g].leftMargin = val
                editor.clear_history()

            return times

        times = benchmark_deferred_sync()
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        result = {
            "scenario": "deferred_sync_batch",
            "glyph": f"{len(sync_sources)} sources",
            "avg_ms": avg_time * 1000,
            "min_ms": min_time * 1000,
            "max_ms": max_time * 1000,
            "iterations": iterations,
            "depth": 1,
            "descendants": len(sync_targets),
        }
        results.append(result)
        print(f"  Batch: {result['avg_ms']:.3f} ms "
              f"({len(sync_sources)} changes + 1 sync, {len(sync_targets)} affected)")

        # Compare with immediate cascade
        def benchmark_immediate_cascade():
            times = []
            for _ in range(iterations):
                originals = {}
                for g in sync_sources + sync_targets:
                    if g in font:
                        originals[g] = font[g].leftMargin

                start = time.perf_counter()
                for source in sync_sources:
                    cmd = AdjustMarginCommand(source, "left", 5)  # apply_rules=True
                    editor.execute(cmd)
                end = time.perf_counter()

                times.append(end - start)

                for g, val in originals.items():
                    font[g].leftMargin = val
                editor.clear_history()

            return times

        times = benchmark_immediate_cascade()
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        result = {
            "scenario": "immediate_cascade_batch",
            "glyph": f"{len(sync_sources)} sources",
            "avg_ms": avg_time * 1000,
            "min_ms": min_time * 1000,
            "max_ms": max_time * 1000,
            "iterations": iterations,
            "depth": 1,
            "descendants": len(sync_targets),
        }
        results.append(result)
        print(f"  Immediate: {result['avg_ms']:.3f} ms "
              f"({len(sync_sources)} changes with cascade)")

    # =========================================================================
    # Report
    # =========================================================================
    print("\n" + "=" * 60)
    print("PERFORMANCE REPORT")
    print("=" * 60)
    print(f"\nIterations per test: {iterations}")
    print(f"\nResults (sorted by scenario):\n")

    # Group by scenario
    scenarios = {}
    for r in results:
        key = r["scenario"]
        if key not in scenarios:
            scenarios[key] = []
        scenarios[key].append(r)

    for scenario, items in scenarios.items():
        print(f"\n{scenario}:")
        for r in items:
            extras = []
            if "ruled" in r:
                extras.append(f"ruled={r['ruled']}")
            if "propagated" in r:
                extras.append(f"propagated={r['propagated']}")
            extra_str = f" ({', '.join(extras)})" if extras else ""
            print(f"  {r['glyph']}: avg={r['avg_ms']:.3f}ms, "
                  f"min={r['min_ms']:.3f}ms, max={r['max_ms']:.3f}ms "
                  f"[depth={r['depth']}, desc={r['descendants']}]{extra_str}")

    # Summary table
    print("\n" + "-" * 60)
    print("SUMMARY TABLE (avg times in ms)")
    print("-" * 60)
    print(f"{'Scenario':<35} {'Glyph':<12} {'Avg (ms)':<10} {'Depth':<6} {'Desc':<6}")
    print("-" * 60)
    for r in sorted(results, key=lambda x: x['avg_ms']):
        print(f"{r['scenario']:<35} {r['glyph']:<12} {r['avg_ms']:<10.3f} "
              f"{r['depth']:<6} {r['descendants']:<6}")

    return results


if __name__ == "__main__":
    font_path = "/home/alexander/WORK/Evacode/stuff/ClassicismBook-TextRegular.ufo"

    if len(sys.argv) > 1:
        font_path = sys.argv[1]

    iterations = 100
    if len(sys.argv) > 2:
        iterations = int(sys.argv[2])

    run_benchmarks(font_path, iterations)
