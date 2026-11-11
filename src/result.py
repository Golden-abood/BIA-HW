"""Common result container shared by all metaheuristics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class RunResult:
    algorithm: str
    best_value: int
    best_cost: int
    best_solution: np.ndarray
    history: list[int]
    evaluations: int
    iterations: int
    best_iteration: int
    runtime_sec: float
    seed: int
    feasible: bool

    @property
    def selected_count(self) -> int:
        return int(np.count_nonzero(self.best_solution))
