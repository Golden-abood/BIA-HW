"""Feasibility repair and objective evaluation for binary knapsack solutions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .instance import ProjectInstance


@dataclass
class Evaluation:
    value: int
    cost: int
    feasible: bool
    selected: np.ndarray
    selected_count: int


class Evaluator:
    """Shared objective function and repair operator for GA and BPSO."""

    def __init__(self, instance: ProjectInstance) -> None:
        self.instance = instance
        self.n = instance.n
        self.costs = instance.costs
        self.values = instance.values
        self.budget = instance.budget
        ratio = self.values.astype(np.float64) / self.costs.astype(np.float64)
        self.descending_ratio_order = np.argsort(-ratio, kind="stable")
        self.ascending_ratio_order = np.argsort(ratio, kind="stable")

    def repair(self, x: np.ndarray) -> np.ndarray:
        """Return a feasible solution using ratio-based removal and prefix greedy fill."""
        selected = np.asarray(x, dtype=bool).reshape(-1).copy()
        if selected.shape != (self.n,):
            raise ValueError("Solution has an invalid shape.")

        cost = int(self.costs[selected].sum())
        if cost > self.budget:
            excess = cost - self.budget
            ascending_selected = self.ascending_ratio_order[selected[self.ascending_ratio_order]]
            cumulative = np.cumsum(self.costs[ascending_selected])
            remove_count = int(np.searchsorted(cumulative, excess, side="left")) + 1
            selected[ascending_selected[:remove_count]] = False
            cost -= int(cumulative[remove_count - 1])

        capacity_left = self.budget - cost
        if capacity_left > 0:
            remaining = self.descending_ratio_order[~selected[self.descending_ratio_order]]
            if remaining.size > 0:
                cumulative = np.cumsum(self.costs[remaining])
                add_count = int(np.searchsorted(cumulative, capacity_left, side="right"))
                if add_count > 0:
                    selected[remaining[:add_count]] = True
                    cost += int(cumulative[add_count - 1])

        return selected

    def evaluate(self, x: np.ndarray, repair: bool = True) -> Evaluation:
        selected = self.repair(x) if repair else np.asarray(x, dtype=bool).reshape(-1).copy()
        if selected.shape != (self.n,):
            raise ValueError("Solution has an invalid shape.")
        cost = int(self.costs[selected].sum())
        value = int(self.values[selected].sum())
        return Evaluation(
            value=value,
            cost=cost,
            feasible=cost <= self.budget,
            selected=selected,
            selected_count=int(np.count_nonzero(selected)),
        )
