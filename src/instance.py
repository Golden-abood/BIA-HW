"""Project-instance generation, validation, and JSON persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from config import (
    BUDGET_FRACTION,
    COST_RANGE,
    INSTANCE_SEEDS,
    INSTANCES_DIR,
    SIZE_PROJECTS,
    VALUE_RANGE,
)


@dataclass
class ProjectInstance:
    name: str
    n: int
    costs: np.ndarray
    values: np.ndarray
    budget: int
    seed: int
    budget_fraction: float = BUDGET_FRACTION

    def __post_init__(self) -> None:
        self.costs = np.asarray(self.costs, dtype=np.int64)
        self.values = np.asarray(self.values, dtype=np.int64)
        self.budget = int(self.budget)
        self.n = int(self.n)
        self.seed = int(self.seed)
        self._validate()

    def _validate(self) -> None:
        if self.n <= 0:
            raise ValueError("The number of projects must be positive.")
        if self.costs.shape != (self.n,) or self.values.shape != (self.n,):
            raise ValueError("costs and values must have exactly n elements.")
        if np.any(self.costs <= 0) or np.any(self.values <= 0):
            raise ValueError("All costs and values must be positive.")
        if self.budget <= 0:
            raise ValueError("The budget must be positive.")
        if self.budget >= int(self.costs.sum()):
            raise ValueError("The budget must be strictly smaller than the total cost.")

    @property
    def total_cost(self) -> int:
        return int(self.costs.sum())

    @property
    def total_value(self) -> int:
        return int(self.values.sum())

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "n": self.n,
            "costs": [int(value) for value in self.costs],
            "values": [int(value) for value in self.values],
            "budget": self.budget,
            "seed": self.seed,
            "budget_fraction": self.budget_fraction,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ProjectInstance":
        return cls(
            name=str(payload["name"]),
            n=int(payload["n"]),
            costs=np.asarray(payload["costs"], dtype=np.int64),
            values=np.asarray(payload["values"], dtype=np.int64),
            budget=int(payload["budget"]),
            seed=int(payload["seed"]),
            budget_fraction=float(payload.get("budget_fraction", BUDGET_FRACTION)),
        )


def generate_instance(
    name: str,
    n: int,
    seed: int,
    cost_range: tuple[int, int] = COST_RANGE,
    value_range: tuple[int, int] = VALUE_RANGE,
    budget_fraction: float = BUDGET_FRACTION,
) -> ProjectInstance:
    """Generate a reproducible uncorrelated 0/1 knapsack instance."""
    if n <= 0:
        raise ValueError("n must be positive.")
    if not 0 < budget_fraction < 1:
        raise ValueError("budget_fraction must be in (0, 1).")

    rng = np.random.default_rng(seed)
    costs = rng.integers(cost_range[0], cost_range[1] + 1, size=n, dtype=np.int64)
    values = rng.integers(value_range[0], value_range[1] + 1, size=n, dtype=np.int64)
    budget = int(round(budget_fraction * int(costs.sum())))
    return ProjectInstance(
        name=name,
        n=n,
        costs=costs,
        values=values,
        budget=budget,
        seed=seed,
        budget_fraction=budget_fraction,
    )


def save_instance(instance: ProjectInstance, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(instance.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_instance(path: Path) -> ProjectInstance:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ProjectInstance.from_dict(payload)


def ensure_instances(force: bool = False) -> dict[str, ProjectInstance]:
    """Create or load the three documented instances used in the experiments."""
    instances: dict[str, ProjectInstance] = {}
    for size_name in SIZE_PROJECTS:
        path = INSTANCES_DIR / f"{size_name}.json"
        expected_n = SIZE_PROJECTS[size_name]
        expected_seed = INSTANCE_SEEDS[size_name]
        if path.exists() and not force:
            instance = load_instance(path)
            if instance.n != expected_n or instance.seed != expected_seed:
                instance = generate_instance(size_name, expected_n, expected_seed)
                save_instance(instance, path)
        else:
            instance = generate_instance(size_name, expected_n, expected_seed)
            save_instance(instance, path)
        instances[size_name] = instance
    return instances
