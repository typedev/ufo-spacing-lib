"""
Metrics Rules Constants.

This module defines constants used throughout the metrics rules system.
"""

# Storage key for font.lib
METRICS_RULES_LIB_KEY = "com.typedev.spacing.metricsRules"

# Current version of the rules format
METRICS_RULES_VERSION = 1

# Rule sides
SIDE_LEFT = "left"
SIDE_RIGHT = "right"
SIDE_BOTH = "both"

# Source side indicators (used in ParsedRule)
SOURCE_SIDE_SAME = "same"      # Same side as target (default)
SOURCE_SIDE_OPPOSITE = "opposite"  # Opposite side (for =H| syntax)
