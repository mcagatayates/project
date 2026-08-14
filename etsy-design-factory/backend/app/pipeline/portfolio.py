"""Largest-remainder allocation: splits an integer target across fractional
buckets so the parts always sum exactly to the target, with no bucket
silently dropped to zero unless its configured fraction actually is zero."""

from __future__ import annotations


def allocate(target: int, fractions: dict[str, float]) -> dict[str, int]:
    total_fraction = sum(fractions.values()) or 1.0
    raw = {bucket: target * (frac / total_fraction) for bucket, frac in fractions.items()}
    floors = {bucket: int(value) for bucket, value in raw.items()}
    remainder = target - sum(floors.values())

    remainders = sorted(raw.items(), key=lambda kv: raw[kv[0]] - floors[kv[0]], reverse=True)
    allocation = dict(floors)
    for bucket, _ in remainders[:remainder]:
        allocation[bucket] += 1
    return allocation


def scale_down(allocation: dict[str, int], factor: float) -> dict[str, int]:
    """Proportionally shrink an allocation (e.g. under a tight budget)
    without necessarily zeroing any single bucket, by re-running the same
    largest-remainder split against the reduced total."""
    if factor >= 1.0:
        return dict(allocation)
    total = sum(allocation.values())
    new_target = max(0, round(total * factor))
    fractions = {bucket: (count / total if total else 0) for bucket, count in allocation.items()}
    return allocate(new_target, fractions)
