"""Command-line entry point for all experiments."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from config import ALGORITHM_NAMES, DEFAULT_MAX_EVALUATIONS, DEFAULT_RUNS, MASTER_SEED, SIZE_NAMES
from src.experiments import run_experiments


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GA, BPSO, ACO, and DP on 0/1 knapsack instances.")
    parser.add_argument("--sizes", nargs="+", choices=SIZE_NAMES, default=list(SIZE_NAMES))
    parser.add_argument("--algorithms", nargs="+", choices=ALGORITHM_NAMES, default=list(ALGORITHM_NAMES))
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--max-evals", type=int, default=DEFAULT_MAX_EVALUATIONS)
    parser.add_argument("--seed", type=int, default=MASTER_SEED)
    parser.add_argument("--output", default="results")
    parser.add_argument("--quick", action="store_true", help="Small smoke-test run (small instance, 2 runs, 1000 evaluations).")
    parser.add_argument("--rebuild-instances", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    if not output_dir.is_absolute():
        output_dir = PROJECT_DIR / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(output_dir / "run.log", mode="w", encoding="utf-8"),
        ],
    )

    paths = run_experiments(
        sizes=args.sizes,
        algorithms=args.algorithms,
        runs=args.runs,
        max_evaluations=args.max_evals,
        output_dir=output_dir,
        master_seed=args.seed,
        quick=args.quick,
        rebuild_instances=args.rebuild_instances,
    )
    print(json.dumps({key: str(value) for key, value in paths.items()}, indent=2))


if __name__ == "__main__":
    main()
