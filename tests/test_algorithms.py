from __future__ import annotations

import unittest
from dataclasses import replace

from config import ALGORITHM_CONFIGS
from src.aco import run_aco
from src.dp import solve_dp
from src.ga import run_ga
from src.instance import generate_instance
from src.pso import run_bpso


class TestAlgorithms(unittest.TestCase):
    def setUp(self) -> None:
        self.instance = generate_instance("tiny", 12, 123)
        self.optimum = solve_dp(self.instance).optimal_value

    def _config(self, algorithm: str):
        base = ALGORITHM_CONFIGS[algorithm]
        if algorithm == "GA":
            return replace(base, population_size=10, max_evaluations=300)
        if algorithm == "BPSO":
            return replace(base, swarm_size=10, max_evaluations=300)
        return replace(base, colony_size=10, max_evaluations=300)

    def test_ga(self) -> None:
        result = run_ga(self.instance, self._config("GA"), 42)
        self._check_result(result)

    def test_bpso(self) -> None:
        result = run_bpso(self.instance, self._config("BPSO"), 43)
        self._check_result(result)

    def test_aco(self) -> None:
        result = run_aco(self.instance, self._config("ACO"), 44)
        self._check_result(result)

    def _check_result(self, result) -> None:
        self.assertTrue(result.feasible)
        self.assertLessEqual(result.best_value, self.optimum)
        self.assertGreaterEqual(result.best_value, 0)
        self.assertGreater(result.evaluations, 0)
        self.assertLessEqual(result.evaluations, 300)
        self.assertGreaterEqual(result.best_cost, 0)
        self.assertLessEqual(result.best_cost, self.instance.budget)
        self.assertEqual(result.best_cost, int(self.instance.costs[result.best_solution].sum()))
        self.assertTrue(all(a <= b for a, b in zip(result.history, result.history[1:])))

    def test_determinism(self) -> None:
        first = run_ga(self.instance, self._config("GA"), 99)
        second = run_ga(self.instance, self._config("GA"), 99)
        self.assertEqual(first.best_value, second.best_value)
        self.assertEqual(first.history, second.history)
        self.assertEqual(first.evaluations, second.evaluations)

        first = run_bpso(self.instance, self._config("BPSO"), 99)
        second = run_bpso(self.instance, self._config("BPSO"), 99)
        self.assertEqual(first.best_value, second.best_value)
        self.assertEqual(first.history, second.history)

        first = run_aco(self.instance, self._config("ACO"), 99)
        second = run_aco(self.instance, self._config("ACO"), 99)
        self.assertEqual(first.best_value, second.best_value)
        self.assertEqual(first.history, second.history)


if __name__ == "__main__":
    unittest.main()
