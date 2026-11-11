"""Experiment orchestration and CSV persistence."""

from __future__ import annotations

import csv
import json
import logging
import platform
import sys
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

import numpy as np

from config import (
    ALGORITHM_CONFIGS,
    ALGORITHM_NAMES,
    BUDGET_FRACTION,
    COST_RANGE,
    DEFAULT_MAX_EVALUATIONS,
    DEFAULT_RUNS,
    INSTANCE_SEEDS,
    MASTER_SEED,
    SIZE_NAMES,
    SIZE_PROJECTS,
    VALUE_RANGE,
    ensure_directories,
    run_seed,
)

from .aco import run_aco
from .analysis import summarize_raw, write_summary_csv, write_summary_markdown
from .dp import solve_dp
from .ga import run_ga
from .instance import ensure_instances
from .pso import run_bpso
from .result import RunResult

LOGGER = logging.getLogger(__name__)

RAW_COLUMNS = [
    "size",
    "instance",
    "n",
    "budget",
    "algorithm",
    "run",
    "seed",
    "best_value",
    "best_cost",
    "selected_count",
    "optimal_value",
    "gap_pct",
    "runtime_sec",
    "evaluations",
    "iterations",
    "best_iteration",
    "feasible",
]

CONVERGENCE_COLUMNS = [
    "size",
    "algorithm",
    "run",
    "iteration",
    "best_fitness",
]

DP_COLUMNS = [
    "size",
    "instance",
    "n",
    "budget",
    "total_cost",
    "optimal_value",
    "runtime_sec",
    "memory_bytes",
]


def _run_algorithm(instance, algorithm: str, config, seed: int) -> RunResult:
    if algorithm == "GA":
        return run_ga(instance, config, seed)
    if algorithm == "BPSO":
        return run_bpso(instance, config, seed)
    if algorithm == "ACO":
        return run_aco(instance, config, seed)
    raise ValueError(f"Unknown algorithm: {algorithm}")


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_experiments(
    sizes: list[str] | None = None,
    algorithms: list[str] | None = None,
    runs: int = DEFAULT_RUNS,
    max_evaluations: int = DEFAULT_MAX_EVALUATIONS,
    output_dir: Path | str = "results",
    master_seed: int = MASTER_SEED,
    quick: bool = False,
    rebuild_instances: bool = False,
) -> dict[str, Path]:
    """Run the full experimental protocol and write all result files."""
    ensure_directories()
    if quick:
        sizes = ["small"]
        runs = min(runs, 2)
        max_evaluations = min(max_evaluations, 1_000)

    sizes = list(sizes) if sizes else list(SIZE_NAMES)
    algorithms = list(algorithms) if algorithms else list(ALGORITHM_NAMES)
    for size in sizes:
        if size not in SIZE_PROJECTS:
            raise ValueError(f"Unknown size: {size}")
    for algorithm in algorithms:
        if algorithm not in ALGORITHM_NAMES:
            raise ValueError(f"Unknown algorithm: {algorithm}")
    if runs <= 0 or max_evaluations <= 0:
        raise ValueError("runs and max_evaluations must be positive.")

    output_dir = Path(output_dir)
    if not output_dir.is_absolute():
        output_dir = Path(__file__).resolve().parent.parent / output_dir
    figures_dir = output_dir / "figures"
    tables_dir = output_dir / "tables"
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    instances = ensure_instances(force=rebuild_instances)

    raw_rows: list[dict] = []
    convergence_rows: list[dict] = []
    dp_rows: list[dict] = []

    for size in sizes:
        instance = instances[size]
        LOGGER.info("Solving exact DP baseline for %s instance (n=%d, budget=%d)", size, instance.n, instance.budget)
        dp_result = solve_dp(instance, reconstruct=False)
        dp_rows.append(
            {
                "size": size,
                "instance": instance.name,
                "n": instance.n,
                "budget": instance.budget,
                "total_cost": instance.total_cost,
                "optimal_value": dp_result.optimal_value,
                "runtime_sec": dp_result.runtime_sec,
                "memory_bytes": dp_result.memory_bytes,
            }
        )
        LOGGER.info("DP optimum for %s: %d", size, dp_result.optimal_value)

        for algorithm in algorithms:
            config = replace(ALGORITHM_CONFIGS[algorithm], max_evaluations=max_evaluations)
            for run_index in range(runs):
                seed = run_seed(size, algorithm, run_index, master_seed)
                LOGGER.info("Running %s on %s, run %d/%d (seed=%d)", algorithm, size, run_index + 1, runs, seed)
                result = _run_algorithm(instance, algorithm, config, seed)
                gap = 0.0 if dp_result.optimal_value == 0 else 100.0 * (
                    dp_result.optimal_value - result.best_value
                ) / dp_result.optimal_value
                raw_rows.append(
                    {
                        "size": size,
                        "instance": instance.name,
                        "n": instance.n,
                        "budget": instance.budget,
                        "algorithm": algorithm,
                        "run": run_index,
                        "seed": seed,
                        "best_value": result.best_value,
                        "best_cost": result.best_cost,
                        "selected_count": result.selected_count,
                        "optimal_value": dp_result.optimal_value,
                        "gap_pct": gap,
                        "runtime_sec": result.runtime_sec,
                        "evaluations": result.evaluations,
                        "iterations": result.iterations,
                        "best_iteration": result.best_iteration,
                        "feasible": result.feasible,
                    }
                )
                for iteration, value in enumerate(result.history):
                    convergence_rows.append(
                        {
                            "size": size,
                            "algorithm": algorithm,
                            "run": run_index,
                            "iteration": iteration,
                            "best_fitness": value,
                        }
                    )

    raw_path = output_dir / "raw_results.csv"
    convergence_path = output_dir / "convergence.csv"
    dp_path = output_dir / "dp_results.csv"
    summary_path = output_dir / "summary.csv"
    summary_md_path = tables_dir / "summary.md"
    config_path = output_dir / "config.json"

    _write_csv(raw_path, RAW_COLUMNS, raw_rows)
    _write_csv(convergence_path, CONVERGENCE_COLUMNS, convergence_rows)
    _write_csv(dp_path, DP_COLUMNS, dp_rows)

    summaries = summarize_raw(raw_rows)
    write_summary_csv(summaries, summary_path)
    write_summary_markdown(summaries, summary_md_path)

    config_payload = {
        "project": "Project Budget Allocation (0/1 Knapsack)",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "platform": platform.platform(),
        "master_seed": master_seed,
        "seed_formula": "master_seed + 1000*size_index + 100*algorithm_index + run_index",
        "sizes": {size: SIZE_PROJECTS[size] for size in sizes},
        "instance_seeds": {size: INSTANCE_SEEDS[size] for size in sizes},
        "budget_fraction": BUDGET_FRACTION,
        "cost_range": COST_RANGE,
        "value_range": VALUE_RANGE,
        "runs": runs,
        "max_evaluations": max_evaluations,
        "algorithms": {
            algorithm: asdict(replace(ALGORITHM_CONFIGS[algorithm], max_evaluations=max_evaluations))
            for algorithm in algorithms
        },
        "instance_files": {size: str(Path("data") / "instances" / f"{size}.json") for size in sizes},
    }
    config_path.write_text(json.dumps(config_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    LOGGER.info("Wrote results to %s", output_dir)
    return {
        "raw": raw_path,
        "convergence": convergence_path,
        "dp": dp_path,
        "summary": summary_path,
        "summary_md": summary_md_path,
        "config": config_path,
        "figures_dir": figures_dir,
    }
