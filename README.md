# Project Budget Allocation (0/1 Knapsack)

A complete, reproducible optimization project that selects a subset of candidate projects under a fixed budget. It implements **Genetic Algorithm (GA)**, **Binary Particle Swarm Optimization (BPSO)**, and **Ant Colony Optimization (ACO)** from scratch, plus an exact **Dynamic Programming (DP)** baseline for optimality-gap measurement.

## Problem

Given `n` projects, each with an integer cost `c_i` and an expected value `v_i`, choose a binary vector `x_i` that maximizes total value without exceeding budget `B`:

```text
maximize    sum(v_i * x_i)
subject to  sum(c_i * x_i) <= B
            x_i in {0, 1}
```

The project is framed as a realistic **project portfolio / budget allocation** problem. Costs and values are deterministic estimates and projects are indivisible.

## Algorithms

All three metaheuristics are implemented directly in Python; no third-party optimizer library is used.

| Algorithm | Representation | Key mechanism |
|---|---|---|
| GA | Binary chromosome | Tournament selection, uniform crossover, bit-flip mutation, elitism, repair/fill |
| BPSO | Binary position, real velocity | Sigmoid transfer, `pbest`/`gbest`, decreasing inertia, repair/fill |
| ACO | Probabilistic solution construction | Pheromone per project, value/cost heuristic, evaporation and best-solution deposits, pheromone bounds |
| DP | Rolling value array | Exact 0/1 knapsack recurrence, `O(nB)` time and `O(B)` value-only memory |

Shared evaluator:
- Objective: total selected value.
- Feasibility: total selected cost must not exceed the budget.
- Repair: remove the selected projects with the lowest value/cost ratio until feasible, then greedily fill remaining capacity. ACO builds feasible solutions directly and then applies the same greedy fill.
- Every returned solution is feasible.

## Project Structure

```text
knapsack_project/
├── README.md
├── requirements.txt
├── config.py
├── run_experiments.py
├── make_report.py
├── src/
│   ├── __init__.py
│   ├── instance.py
│   ├── evaluator.py
│   ├── dp.py
│   ├── ga.py
│   ├── pso.py
│   ├── aco.py
│   ├── experiments.py
│   ├── analysis.py
│   └── plotting.py
├── tests/
│   ├── test_instances.py
│   ├── test_dp.py
│   ├── test_evaluator.py
│   └── test_algorithms.py
├── data/
│   └── instances/
│       ├── small.json
│       ├── medium.json
│       └── large.json
├── results/
│   ├── raw_results.csv
│   ├── convergence.csv
│   ├── summary.csv
│   ├── dp_results.csv
│   ├── config.json
│   ├── run.log
│   ├── figures/
│   └── tables/
└── report/
    ├── report_ar.md
    └── report_ar.docx
```

## Requirements

- Python 3.10+ (tested with Python 3.14)
- NumPy
- Matplotlib
- python-docx (only for generating the Arabic DOCX report)

Install:

```bash
python -m pip install -r requirements.txt
```

If `python` is not on your PATH on Windows, use `py -3` or the full path to your Python executable.

## Quick Start

Run a small smoke test first:

```bash
python run_experiments.py --quick
```

This runs the Small instance with 2 runs and 1,000 evaluations per algorithm. It is intended only to verify the installation; use the full command for the report.

## Full Experiments

```bash
python run_experiments.py
```

Default protocol:
- Sizes: Small (`n=20`), Medium (`n=60`), Large (`n=150`)
- 30 independent runs per algorithm per size (270 metaheuristic runs)
- 25,000 fitness evaluations per run, no early stopping
- Fixed instance seeds: `1001`, `1002`, `1003`
- Master seed: `2026`
- Run seed formula: `2026 + 1000*size_index + 100*algorithm_index + run_index`

On the tested machine the full run takes about 3 minutes.

Useful options:

```bash
python run_experiments.py --sizes small medium --algorithms GA BPSO --runs 5
python run_experiments.py --max-evals 10000 --output results_dev
python run_experiments.py --rebuild-instances
```

## Generate the Report and Figures

```bash
python make_report.py
```

Outputs:
- `report/report_ar.docx` — Arabic report with cover, tables, figures, team placeholders, and references
- `report/report_ar.md` — Markdown source of the report
- `results/figures/` — updated PNG figures

The report is generated from the actual CSV results. Run the full experiments before generating the final report.

## Output Files

| File | Description |
|---|---|
| `results/raw_results.csv` | One row per metaheuristic run: value, cost, gap, runtime, evaluations, iterations, feasibility |
| `results/convergence.csv` | Best-so-far fitness after every iteration for every run |
| `results/dp_results.csv` | Exact optimum, DP runtime, and DP memory for each size |
| `results/summary.csv` | Aggregated best/mean/std/median/worst, gaps, runtimes, feasibility, win counts, 95% CI |
| `results/config.json` | Seeds, hyperparameters, instance metadata, Python/NumPy versions, platform |
| `results/run.log` | Timestamped execution log |
| `results/figures/convergence_small.png` | Convergence on the Small instance |
| `results/figures/convergence_medium.png` | Convergence on the Medium instance |
| `results/figures/convergence_large.png` | Convergence on the Large instance |
| `results/figures/boxplots.png` | Stability of final best fitness across runs |
| `results/figures/gap_comparison.png` | Mean optimality gap by size and algorithm |
| `results/figures/runtime_comparison.png` | Mean runtime by size and algorithm |

## Reproducibility

- Instance generation and every algorithm run use documented seeds.
- Instances are saved as JSON in `data/instances/` and reloaded on later runs.
- Hyperparameters and the seed formula are saved in `results/config.json`.
- Each run logs its seed, evaluations, iterations, and feasibility.
- Re-running with the same seeds produces identical values and histories.

## Testing

Run the unit tests from the project directory:

```bash
python -m unittest discover -s tests -v
```

The suite covers:
- DP versus exhaustive brute force on tiny instances
- DP reconstruction feasibility and optimality
- Repair feasibility and evaluation consistency
- Instance generation reproducibility and JSON round-trip
- GA/BPSO/ACO feasibility, monotonic convergence history, and deterministic behavior

## Configuration

Main settings are in `config.py`:
- `SIZE_PROJECTS`: `20`, `60`, `150`
- `INSTANCE_SEEDS`: `1001`, `1002`, `1003`
- `COST_RANGE`, `VALUE_RANGE`: `[100, 1000]`
- `BUDGET_FRACTION`: `0.50`
- `MASTER_SEED`: `2026`
- `DEFAULT_RUNS`: `30`
- `DEFAULT_MAX_EVALUATIONS`: `25,000`
- Algorithm dataclasses: `GAConfig`, `BPSOConfig`, `ACOConfig`

## Hyperparameters

| Parameter | GA | BPSO | ACO |
|---|---:|---:|---:|
| Population / swarm / colony | 50 | 50 | 50 |
| Evaluation budget | 25,000 | 25,000 | 25,000 |
| Selection | Tournament `k=3` | — | — |
| Crossover | Uniform `p_c=0.9` | — | — |
| Mutation | Bit-flip `p_m=1/n` | — | — |
| Elitism | 2 | — | — |
| Inertia `w` | — | `0.9 -> 0.4` | — |
| `c1`, `c2` | — | `1.5`, `1.5` | — |
| `v_max` | — | 6 | — |
| `alpha`, `beta` | — | — | `1`, `2` |
| Evaporation `rho` | — | — | `0.1` |
| Initial pheromone | — | — | `0.5` |
| Pheromone bounds | — | — | `[0.01, 1.0]` |
| Stopping | 25,000 evaluations | 25,000 evaluations | 25,000 evaluations |

## Notes on Fairness

- All metaheuristics use the same instances, objective function, repair/fill operator, and 25,000-evaluation budget.
- No early stopping is used, so every run consumes the same evaluation budget.
- DP is used only to compute the optimal value and gap; it is never consulted inside GA, BPSO, or ACO.
- Hyperparameters are fixed before the experiments and are not tuned per instance or per run.
- Runtime includes optimization, repair, and fitness evaluation; it excludes file I/O and plotting.

## Scope and Limitations

- Single budget constraint; no project dependencies or conflicts.
- Synthetic uncorrelated instances with fixed seeds.
- One instance per size, 30 independent runs per algorithm.
- Fixed hyperparameters; no per-size tuning.
- These choices keep the project focused and reproducible; see the report's discussion for threats to validity and future work.
