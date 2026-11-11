"""Aggregation of raw experiment results into report-ready summaries."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from config import ALGORITHM_NAMES, SIZE_NAMES


SUMMARY_COLUMNS = [
    "size",
    "algorithm",
    "runs",
    "best_value",
    "mean_value",
    "std_value",
    "median_value",
    "worst_value",
    "best_gap_pct",
    "mean_gap_pct",
    "std_gap_pct",
    "median_gap_pct",
    "mean_runtime_sec",
    "std_runtime_sec",
    "min_runtime_sec",
    "max_runtime_sec",
    "feasible_rate_pct",
    "mean_evaluations",
    "mean_iterations",
    "mean_best_iteration",
    "mean_selected_count",
    "mean_cost",
    "win_count",
    "ci95_value",
]


def read_csv_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def summarize_raw(raw_rows: list[dict]) -> list[dict]:
    summaries: list[dict] = []
    for size in SIZE_NAMES:
        size_rows = [row for row in raw_rows if row["size"] == size]
        if not size_rows:
            continue
        best_known = max(float(row["best_value"]) for row in size_rows)
        for algorithm in ALGORITHM_NAMES:
            rows = [row for row in size_rows if row["algorithm"] == algorithm]
            if not rows:
                continue
            values = np.asarray([float(row["best_value"]) for row in rows], dtype=np.float64)
            gaps = np.asarray([float(row["gap_pct"]) for row in rows], dtype=np.float64)
            runtimes = np.asarray([float(row["runtime_sec"]) for row in rows], dtype=np.float64)
            evaluations = np.asarray([float(row["evaluations"]) for row in rows], dtype=np.float64)
            iterations = np.asarray([float(row["iterations"]) for row in rows], dtype=np.float64)
            best_iterations = np.asarray([float(row["best_iteration"]) for row in rows], dtype=np.float64)
            selected_counts = np.asarray([float(row["selected_count"]) for row in rows], dtype=np.float64)
            costs = np.asarray([float(row["best_cost"]) for row in rows], dtype=np.float64)
            feasible = np.asarray([1.0 if str(row["feasible"]).lower() in {"true", "1"} else 0.0 for row in rows])
            count = len(rows)
            value_std = float(np.std(values, ddof=1)) if count > 1 else 0.0
            runtime_std = float(np.std(runtimes, ddof=1)) if count > 1 else 0.0
            gap_std = float(np.std(gaps, ddof=1)) if count > 1 else 0.0
            ci95 = 1.96 * value_std / np.sqrt(count) if count > 0 else 0.0
            summaries.append(
                {
                    "size": size,
                    "algorithm": algorithm,
                    "runs": count,
                    "best_value": int(np.max(values)),
                    "mean_value": float(np.mean(values)),
                    "std_value": value_std,
                    "median_value": float(np.median(values)),
                    "worst_value": int(np.min(values)),
                    "best_gap_pct": float(np.min(gaps)),
                    "mean_gap_pct": float(np.mean(gaps)),
                    "std_gap_pct": gap_std,
                    "median_gap_pct": float(np.median(gaps)),
                    "mean_runtime_sec": float(np.mean(runtimes)),
                    "std_runtime_sec": runtime_std,
                    "min_runtime_sec": float(np.min(runtimes)),
                    "max_runtime_sec": float(np.max(runtimes)),
                    "feasible_rate_pct": float(100.0 * np.mean(feasible)),
                    "mean_evaluations": float(np.mean(evaluations)),
                    "mean_iterations": float(np.mean(iterations)),
                    "mean_best_iteration": float(np.mean(best_iterations)),
                    "mean_selected_count": float(np.mean(selected_counts)),
                    "mean_cost": float(np.mean(costs)),
                    "win_count": int(np.sum(values == best_known)),
                    "ci95_value": float(ci95),
                }
            )
    return summaries


def write_summary_csv(summaries: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        for row in summaries:
            writer.writerow(row)


def write_summary_markdown(summaries: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Experimental Summary",
        "",
        "| Size | Algorithm | Best | Mean | Std | Median | Worst | Mean gap % | Time mean (s) | Feasible % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            "| {size} | {algorithm} | {best_value} | {mean_value:.2f} | {std_value:.2f} | "
            "{median_value:.2f} | {worst_value} | {mean_gap_pct:.3f} | {mean_runtime_sec:.4f} | "
            "{feasible_rate_pct:.1f} |".format(**row)
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
