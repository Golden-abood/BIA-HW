"""Central configuration for the budget-allocation (0/1 knapsack) project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INSTANCES_DIR = DATA_DIR / "instances"
RESULTS_DIR = BASE_DIR / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
TABLES_DIR = RESULTS_DIR / "tables"
REPORT_DIR = BASE_DIR / "report"

PROJECT_TITLE = "Project Budget Allocation using GA, BPSO, ACO and DP"

SIZE_NAMES = ("small", "medium", "large")
SIZE_PROJECTS = {"small": 20, "medium": 60, "large": 150}
INSTANCE_SEEDS = {"small": 1001, "medium": 1002, "large": 1003}

COST_RANGE = (100, 1000)
VALUE_RANGE = (100, 1000)
BUDGET_FRACTION = 0.50

MASTER_SEED = 2026
DEFAULT_RUNS = 30
DEFAULT_MAX_EVALUATIONS = 25_000

ALGORITHM_NAMES = ("GA", "BPSO", "ACO")

PLOT_COLORS = {
    "GA": "#1f77b4",
    "BPSO": "#ff7f0e",
    "ACO": "#2ca02c",
}

PLOT_LABELS = {
    "GA": "GA",
    "BPSO": "BPSO",
    "ACO": "ACO",
}


@dataclass(frozen=True)
class GAConfig:
    population_size: int = 50
    tournament_size: int = 3
    crossover_prob: float = 0.9
    mutation_prob: float | None = None
    elitism: int = 2
    max_evaluations: int = DEFAULT_MAX_EVALUATIONS


@dataclass(frozen=True)
class BPSOConfig:
    swarm_size: int = 50
    inertia_start: float = 0.9
    inertia_end: float = 0.4
    c1: float = 1.5
    c2: float = 1.5
    vmax: float = 6.0
    max_evaluations: int = DEFAULT_MAX_EVALUATIONS


@dataclass(frozen=True)
class ACOConfig:
    colony_size: int = 50
    alpha: float = 1.0
    beta: float = 2.0
    rho: float = 0.1
    tau0: float = 0.5
    tau_min: float = 0.01
    tau_max: float = 1.0
    iteration_weight: float = 0.3
    global_weight: float = 0.7
    max_evaluations: int = DEFAULT_MAX_EVALUATIONS


ALGORITHM_CONFIGS = {
    "GA": GAConfig(),
    "BPSO": BPSOConfig(),
    "ACO": ACOConfig(),
}


def run_seed(size_name: str, algorithm: str, run_index: int, master_seed: int = MASTER_SEED) -> int:
    """Return a documented deterministic seed for one experimental run."""
    size_index = SIZE_NAMES.index(size_name)
    algorithm_index = ALGORITHM_NAMES.index(algorithm)
    return master_seed + 1000 * size_index + 100 * algorithm_index + run_index


def ensure_directories() -> None:
    for directory in (DATA_DIR, INSTANCES_DIR, RESULTS_DIR, FIGURES_DIR, TABLES_DIR, REPORT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
