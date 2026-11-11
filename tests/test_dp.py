from __future__ import annotations

import unittest

import numpy as np

from src.dp import brute_force, solve_dp
from src.instance import ProjectInstance, generate_instance


class TestDynamicProgramming(unittest.TestCase):
    def test_dp_matches_brute_force(self) -> None:
        for seed in range(10):
            instance = generate_instance("tiny", 12, seed)
            dp_result = solve_dp(instance)
            brute_value, brute_selected = brute_force(instance)
            self.assertEqual(dp_result.optimal_value, brute_value)
            self.assertAlmostEqual(
                float(instance.values[brute_selected].sum()),
                float(brute_value),
            )

    def test_reconstruction_is_optimal_and_feasible(self) -> None:
        for seed in range(5):
            instance = generate_instance("tiny", 14, seed)
            result = solve_dp(instance, reconstruct=True)
            self.assertIsNotNone(result.selected)
            selected = result.selected
            self.assertLessEqual(int(instance.costs[selected].sum()), instance.budget)
            self.assertEqual(int(instance.values[selected].sum()), result.optimal_value)

    def test_item_heavier_than_budget(self) -> None:
        instance = ProjectInstance(
            name="edge",
            n=2,
            costs=np.array([10, 100], dtype=np.int64),
            values=np.array([50, 500], dtype=np.int64),
            budget=20,
            seed=1,
        )
        result = solve_dp(instance, reconstruct=True)
        self.assertEqual(result.optimal_value, 50)
        self.assertIsNotNone(result.selected)
        self.assertLessEqual(int(instance.costs[result.selected].sum()), instance.budget)

    def test_empty_selection_when_nothing_fits(self) -> None:
        instance = ProjectInstance(
            name="edge",
            n=1,
            costs=np.array([100], dtype=np.int64),
            values=np.array([500], dtype=np.int64),
            budget=50,
            seed=2,
        )
        result = solve_dp(instance, reconstruct=True)
        self.assertEqual(result.optimal_value, 0)
        self.assertIsNotNone(result.selected)
        self.assertFalse(bool(result.selected[0]))


if __name__ == "__main__":
    unittest.main()
