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


def checked_time_advance(current_h: float, delta_h: float) -> float:
    """Return a representable later model time in hours, or fail before mutation."""

    if isinstance(current_h, bool) or isinstance(delta_h, bool):
        raise ValueError("模拟时钟无法安全推进；请重置或载入有效状态。")
    try:
        current = float(current_h)
        delta = float(delta_h)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("模拟时钟无法安全推进；请重置或载入有效状态。") from None
    if not isfinite(current) or current < 0.0 or not isfinite(delta) or delta <= 0.0:
        raise ValueError("模拟时钟无法安全推进；请重置或载入有效状态。")
    next_time = current + delta
    if not isfinite(next_time) or next_time <= current:
        raise ValueError("模拟时钟无法安全推进；请重置或载入有效状态。")
    return next_time
