"""Matplotlib figures for convergence, stability, quality, and runtime."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from config import ALGORITHM_NAMES, PLOT_COLORS, SIZE_NAMES

from .analysis import read_csv_rows


def _convergence_groups(rows: list[dict]) -> dict[tuple[str, str], list[np.ndarray]]:
    grouped: dict[tuple[str, str], dict[int, list[tuple[int, int]]]] = {}
    for row in rows:
        size = row["size"]
        algorithm = row["algorithm"]
        run = int(row["run"])
        iteration = int(row["iteration"])
        value = int(row["best_fitness"])
        grouped.setdefault((size, algorithm), {}).setdefault(run, []).append((iteration, value))

    histories: dict[tuple[str, str], list[np.ndarray]] = {}
    for key, runs in grouped.items():
        series = []
        for run in sorted(runs):
            points = sorted(runs[run])
            series.append(np.asarray([value for _, value in points], dtype=np.float64))
        histories[key] = series
    return histories


def _dp_optima(rows: list[dict]) -> dict[str, int]:
    return {row["size"]: int(row["optimal_value"]) for row in rows}


def plot_convergence(
    convergence_rows: list[dict],
    dp_rows: list[dict],
    figures_dir: Path,
) -> list[Path]:
    histories = _convergence_groups(convergence_rows)
    optima = _dp_optima(dp_rows)
    paths: list[Path] = []

    for size in SIZE_NAMES:
        if not any(key[0] == size for key in histories):
            continue
        figure, axis = plt.subplots(figsize=(8.5, 5.0), constrained_layout=True)
        for algorithm in ALGORITHM_NAMES:
            series = histories.get((size, algorithm))
            if not series:
                continue
            min_length = min(len(item) for item in series)
            stacked = np.vstack([item[:min_length] for item in series])
            iterations = np.arange(min_length)
            mean = np.mean(stacked, axis=0)
            std = np.std(stacked, axis=0, ddof=1) if stacked.shape[0] > 1 else np.zeros(min_length)
            color = PLOT_COLORS[algorithm]
            axis.plot(iterations, mean, label=algorithm, color=color, linewidth=2.0)
            axis.fill_between(iterations, mean - std, mean + std, color=color, alpha=0.18, linewidth=0)

        optimum = optima.get(size)
        if optimum is not None:
            axis.axhline(
                optimum,
                color="#444444",
                linestyle="--",
                linewidth=1.3,
                label=f"DP optimum ({optimum})",
            )
        axis.set_title(f"Convergence on the {size.capitalize()} instance")
        axis.set_xlabel("Iteration")
        axis.set_ylabel("Best fitness (total value)")
        axis.grid(True, alpha=0.3)
        axis.legend(frameon=False)
        path = figures_dir / f"convergence_{size}.png"
        figure.savefig(path, dpi=300)
        plt.close(figure)
        paths.append(path)
    return paths


def plot_boxplots(raw_rows: list[dict], figures_dir: Path) -> Path:
    figure, axes = plt.subplots(1, len(SIZE_NAMES), figsize=(15.0, 4.8), constrained_layout=True)
    rng = np.random.default_rng(0)

    for axis, size in zip(np.atleast_1d(axes), SIZE_NAMES):
        data = []
        labels = []
        colors = []
        for algorithm in ALGORITHM_NAMES:
            values = [
                float(row["best_value"])
                for row in raw_rows
                if row["size"] == size and row["algorithm"] == algorithm
            ]
            if values:
                data.append(values)
                labels.append(algorithm)
                colors.append(PLOT_COLORS[algorithm])
        if not data:
            axis.set_visible(False)
            continue
        boxplot = axis.boxplot(
            data,
            tick_labels=labels,
            patch_artist=True,
            widths=0.55,
            showmeans=True,
            meanprops={"marker": "D", "markerfacecolor": "white", "markeredgecolor": "black", "markersize": 5},
        )
        for patch, color in zip(boxplot["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.55)
        for position, values, color in zip(np.arange(1, len(data) + 1), data, colors):
            jitter = rng.uniform(-0.12, 0.12, size=len(values))
            axis.scatter(
                position + jitter,
                values,
                s=14,
                color=color,
                alpha=0.65,
                edgecolor="none",
                zorder=3,
            )
        axis.set_title(size.capitalize())
        axis.set_ylabel("Final best fitness")
        axis.grid(True, axis="y", alpha=0.3)

    figure.suptitle("Stability of final best fitness across independent runs")
    path = figures_dir / "boxplots.png"
    figure.savefig(path, dpi=300)
    plt.close(figure)
    return path


def plot_gap(summary_rows: list[dict], figures_dir: Path) -> Path:
    figure, axis = plt.subplots(figsize=(8.5, 5.0), constrained_layout=True)
    width = 0.8 / len(ALGORITHM_NAMES)
    sizes_present = [size for size in SIZE_NAMES if any(row["size"] == size for row in summary_rows)]
    positions = np.arange(len(sizes_present))

    for index, algorithm in enumerate(ALGORITHM_NAMES):
        values = []
        for size in sizes_present:
            match = [
                row
                for row in summary_rows
                if row["size"] == size and row["algorithm"] == algorithm
            ]
            values.append(float(match[0]["mean_gap_pct"]) if match else 0.0)
        offset = (index - (len(ALGORITHM_NAMES) - 1) / 2.0) * width
        bars = axis.bar(
            positions + offset,
            values,
            width=width,
            label=algorithm,
            color=PLOT_COLORS[algorithm],
        )
        axis.bar_label(bars, fmt="%.2f", fontsize=8, padding=2)

    axis.set_xticks(positions)
    axis.set_xticklabels([size.capitalize() for size in sizes_present])
    axis.set_ylabel("Mean optimality gap (%)")
    axis.set_title("Optimality gap against the exact DP baseline")
    axis.grid(True, axis="y", alpha=0.3)
    axis.legend(frameon=False)
    path = figures_dir / "gap_comparison.png"
    figure.savefig(path, dpi=300)
    plt.close(figure)
    return path


def plot_runtime(summary_rows: list[dict], figures_dir: Path) -> Path:
    figure, axis = plt.subplots(figsize=(8.5, 5.0), constrained_layout=True)
    width = 0.8 / len(ALGORITHM_NAMES)
    sizes_present = [size for size in SIZE_NAMES if any(row["size"] == size for row in summary_rows)]
    positions = np.arange(len(sizes_present))
    all_values: list[float] = []

    for index, algorithm in enumerate(ALGORITHM_NAMES):
        values = []
        for size in sizes_present:
            match = [
                row
                for row in summary_rows
                if row["size"] == size and row["algorithm"] == algorithm
            ]
            values.append(float(match[0]["mean_runtime_sec"]) if match else 0.0)
        all_values.extend(values)
        offset = (index - (len(ALGORITHM_NAMES) - 1) / 2.0) * width
        bars = axis.bar(
            positions + offset,
            values,
            width=width,
            label=algorithm,
            color=PLOT_COLORS[algorithm],
        )
        axis.bar_label(bars, fmt="%.3f", fontsize=8, padding=2)

    positive = [value for value in all_values if value > 0]
    if positive and max(positive) / min(positive) > 30:
        axis.set_yscale("log")
    axis.set_xticks(positions)
    axis.set_xticklabels([size.capitalize() for size in sizes_present])
    axis.set_ylabel("Mean runtime (seconds)")
    axis.set_title("Execution time per algorithm and problem size")
    axis.grid(True, axis="y", alpha=0.3)
    axis.legend(frameon=False)
    path = figures_dir / "runtime_comparison.png"
    figure.savefig(path, dpi=300)
    plt.close(figure)
    return path


def generate_all_figures(results_dir: Path, figures_dir: Path) -> list[Path]:
    raw_rows = read_csv_rows(results_dir / "raw_results.csv")
    convergence_rows = read_csv_rows(results_dir / "convergence.csv")
    dp_rows = read_csv_rows(results_dir / "dp_results.csv")
    summary_rows = read_csv_rows(results_dir / "summary.csv")
    figures_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    paths.extend(plot_convergence(convergence_rows, dp_rows, figures_dir))
    paths.append(plot_boxplots(raw_rows, figures_dir))
    paths.append(plot_gap(summary_rows, figures_dir))
    paths.append(plot_runtime(summary_rows, figures_dir))
    return paths
