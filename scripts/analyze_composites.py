#!/usr/bin/env python3
"""Analyze composite glyphs to find potential issues for rule generation."""

import sys
from pathlib import Path

from defcon import Font


def analyze_composites(font_path: str):
    """Analyze composite glyphs and find potential issues."""
    print(f"Loading font: {font_path}")
    font = Font(font_path)
    print(f"Font loaded: {len(font)} glyphs\n")

    issues = {
        "secondary_wider": [],      # Component 1+ wider than component 0
        "secondary_extends_left": [],  # Component 1+ extends left of component 0
        "secondary_extends_right": [], # Component 1+ extends right of component 0
        "no_base_bounds": [],       # Component 0 has no bounds (empty glyph)
        "multiple_bases": [],       # Multiple non-mark components
        "single_component": [],     # Only one component
        "mixed_contours": [],       # Has both contours and components
    }

    composites = []

    for glyph in font:
        if not glyph.components:
            continue

        comp_count = len(glyph.components)

        # Check for mixed contours + components using controlPointBounds
        # If glyph has bounds beyond what components provide, it has contours
        glyph_bounds = glyph.bounds
        if glyph_bounds and comp_count > 0:
            # Calculate bounds from components only
            comp_bounds = None
            for comp in glyph.components:
                if comp.baseGlyph in font:
                    base = font[comp.baseGlyph]
                    if base.bounds:
                        t = comp.transformation
                        cb = (
                            base.bounds[0] + t[4],
                            base.bounds[1] + t[5],
                            base.bounds[2] + t[4],
                            base.bounds[3] + t[5],
                        )
                        if comp_bounds is None:
                            comp_bounds = cb
                        else:
                            comp_bounds = (
                                min(comp_bounds[0], cb[0]),
                                min(comp_bounds[1], cb[1]),
                                max(comp_bounds[2], cb[2]),
                                max(comp_bounds[3], cb[3]),
                            )

            # If glyph bounds differ significantly from component bounds, has contours
            if comp_bounds:
                tolerance = 2
                has_contours = (
                    abs(glyph_bounds[0] - comp_bounds[0]) > tolerance or
                    abs(glyph_bounds[1] - comp_bounds[1]) > tolerance or
                    abs(glyph_bounds[2] - comp_bounds[2]) > tolerance or
                    abs(glyph_bounds[3] - comp_bounds[3]) > tolerance
                )
                if has_contours:
                    issues["mixed_contours"].append({
                        "glyph": glyph.name,
                        "components": [c.baseGlyph for c in glyph.components],
                        "glyph_bounds": glyph_bounds,
                        "comp_bounds": comp_bounds,
                    })
                    continue

        if comp_count == 1:
            issues["single_component"].append({
                "glyph": glyph.name,
                "base": glyph.components[0].baseGlyph,
            })
            composites.append(glyph.name)
            continue

        composites.append(glyph.name)

        # Get component 0 info
        comp0 = glyph.components[0]
        base0_name = comp0.baseGlyph

        if base0_name not in font:
            continue

        base0 = font[base0_name]
        base0_bounds = base0.bounds

        if base0_bounds is None:
            issues["no_base_bounds"].append({
                "glyph": glyph.name,
                "base": base0_name,
            })
            continue

        # Component 0 bounds with offset applied
        t = comp0.transformation
        comp0_left = base0_bounds[0] + t[4]
        comp0_right = base0_bounds[2] + t[4]
        comp0_width = comp0_right - comp0_left

        # Check other components
        wide_components = []
        left_extending = []
        right_extending = []

        for i, comp in enumerate(glyph.components[1:], 1):
            base_name = comp.baseGlyph
            if base_name not in font:
                continue

            base = font[base_name]
            base_bounds = base.bounds

            if base_bounds is None:
                continue

            t = comp.transformation
            comp_left = base_bounds[0] + t[4]
            comp_right = base_bounds[2] + t[4]
            comp_width = comp_right - comp_left

            # Check if wider
            if comp_width > comp0_width:
                wide_components.append({
                    "index": i,
                    "name": base_name,
                    "width": round(comp_width),
                    "base_width": round(comp0_width),
                })

            # Check if extends left
            if comp_left < comp0_left:
                left_extending.append({
                    "index": i,
                    "name": base_name,
                    "extends_by": round(comp0_left - comp_left),
                })

            # Check if extends right
            if comp_right > comp0_right:
                right_extending.append({
                    "index": i,
                    "name": base_name,
                    "extends_by": round(comp_right - comp0_right),
                })

        if wide_components:
            issues["secondary_wider"].append({
                "glyph": glyph.name,
                "base": base0_name,
                "wider_components": wide_components,
            })

        if left_extending:
            issues["secondary_extends_left"].append({
                "glyph": glyph.name,
                "base": base0_name,
                "extending": left_extending,
            })

        if right_extending:
            issues["secondary_extends_right"].append({
                "glyph": glyph.name,
                "base": base0_name,
                "extending": right_extending,
            })

    # Report
    print("=" * 60)
    print("COMPOSITE ANALYSIS REPORT")
    print("=" * 60)
    print(f"\nTotal composites: {len(composites)}")
    print(f"Single component: {len(issues['single_component'])}")
    print(f"Mixed (contours + components): {len(issues['mixed_contours'])}")

    print("\n" + "-" * 60)
    print("POTENTIAL ISSUES")
    print("-" * 60)

    if issues["secondary_wider"]:
        print(f"\n### Component 1+ WIDER than component 0: {len(issues['secondary_wider'])}")
        for item in issues["secondary_wider"][:10]:
            print(f"  {item['glyph']}: base={item['base']}")
            for wc in item["wider_components"]:
                print(f"    [{wc['index']}] {wc['name']}: {wc['width']} > {wc['base_width']}")

    if issues["secondary_extends_left"]:
        print(f"\n### Component 1+ extends LEFT of component 0: {len(issues['secondary_extends_left'])}")
        for item in issues["secondary_extends_left"][:10]:
            print(f"  {item['glyph']}: base={item['base']}")
            for ext in item["extending"]:
                print(f"    [{ext['index']}] {ext['name']}: -{ext['extends_by']} units")

    if issues["secondary_extends_right"]:
        print(f"\n### Component 1+ extends RIGHT of component 0: {len(issues['secondary_extends_right'])}")
        for item in issues["secondary_extends_right"][:10]:
            print(f"  {item['glyph']}: base={item['base']}")
            for ext in item["extending"]:
                print(f"    [{ext['index']}] {ext['name']}: +{ext['extends_by']} units")

    if issues["no_base_bounds"]:
        print(f"\n### Component 0 has NO BOUNDS: {len(issues['no_base_bounds'])}")
        for item in issues["no_base_bounds"][:10]:
            print(f"  {item['glyph']}: base={item['base']} (empty?)")

    if issues["mixed_contours"]:
        print(f"\n### Mixed contours + components: {len(issues['mixed_contours'])}")
        for item in issues["mixed_contours"][:10]:
            print(f"  {item['glyph']}: components={item['components']}")

    # Summary of issue types
    print("\n" + "-" * 60)
    print("SUMMARY")
    print("-" * 60)
    total_issues = sum(len(v) for v in issues.values())
    print(f"Total glyphs with potential issues: {total_issues}")

    for key, items in issues.items():
        if items:
            print(f"  {key}: {len(items)}")

    return issues


if __name__ == "__main__":
    font_path = "/home/alexander/WORK/Evacode/stuff/ClassicismBook-TextRegular.ufo"
    if len(sys.argv) > 1:
        font_path = sys.argv[1]

    analyze_composites(font_path)
