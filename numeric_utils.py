"""Small numeric helpers shared by relative-state model layers."""

from __future__ import annotations

from math import isfinite


def clamp_finite(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Convert a numeric value to float and clamp it, mapping non-finite values to low.

    Conversion errors intentionally propagate so malformed model inputs are not
    silently treated as valid zero-valued indices.
    """

    numeric = float(value)
    return max(low, min(high, numeric)) if isfinite(numeric) else low
