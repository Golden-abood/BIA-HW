"""Exact 0/1 knapsack solver used as the optimal baseline."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from .instance import ProjectInstance


@dataclass
class DPResult:
    optimal_value: int
    selected: np.ndarray | None
    runtime_sec: float
    memory_bytes: int


def solve_dp(instance: ProjectInstance, reconstruct: bool = False) -> DPResult:
    """Solve 0/1 knapsack exactly with a rolling dynamic-programming array.

    Time complexity is O(n * B) and the value-only memory usage is O(B).
    When reconstruct=True, an additional O(n * B) boolean table is used to
    recover one optimal subset.
    """
    start = time.perf_counter()
    budget = instance.budget
    costs = instance.costs
    values = instance.values

    dp = np.zeros(budget + 1, dtype=np.int64)
    keep = np.zeros((instance.n, budget + 1), dtype=bool) if reconstruct else None

    for index in range(instance.n):
        cost = int(costs[index])
        value = int(values[index])
        if cost > budget:
            continue
        candidate = dp[:-cost] + value
        better = candidate > dp[cost:]
        if keep is not None:
            keep[index, cost:] = better
        dp[cost:] = np.where(better, candidate, dp[cost:])

    optimal_value = int(dp[budget])
    selected = None
    if keep is not None:
        selected = np.zeros(instance.n, dtype=bool)
        remaining = budget
        for index in range(instance.n - 1, -1, -1):
            if keep[index, remaining]:
                selected[index] = True
                remaining -= int(costs[index])

    runtime = time.perf_counter() - start
    memory = int(dp.nbytes + (keep.nbytes if keep is not None else 0))
    return DPResult(
        optimal_value=optimal_value,
        selected=selected,
        runtime_sec=runtime,
        memory_bytes=memory,
    )


def brute_force(instance: ProjectInstance) -> tuple[int, np.ndarray]:
    """Exhaustive solver for small instances, used only to validate the DP."""
    if instance.n > 22:
        raise ValueError("brute_force is intended for tiny instances only.")

    best_value = 0
    best_mask = 0
    for mask in range(1 << instance.n):
        cost = 0
        value = 0
        for index in range(instance.n):
            if mask & (1 << index):
                cost += int(instance.costs[index])
                value += int(instance.values[index])
                if cost > instance.budget:
                    break
        else:
            if value > best_value:
                best_value = value
                best_mask = mask

    selected = np.array([(best_mask >> index) & 1 for index in range(instance.n)], dtype=bool)
    return best_value, selected
