from __future__ import annotations

import unittest

import numpy as np

from src.evaluator import Evaluator
from src.instance import generate_instance


class TestEvaluator(unittest.TestCase):
    def test_repair_is_always_feasible(self) -> None:
        instance = generate_instance("tiny", 30, 77)
        evaluator = Evaluator(instance)
        rng = np.random.default_rng(5)
        for _ in range(100):
            candidate = rng.integers(0, 2, size=instance.n, dtype=np.int8)
            selected = evaluator.repair(candidate)
            cost = int(instance.costs[selected].sum())
            self.assertLessEqual(cost, instance.budget)
            self.assertTrue(np.all((selected == 0) | (selected == 1)))

    def test_all_selected_is_repaired(self) -> None:
        instance = generate_instance("tiny", 30, 78)
        evaluator = Evaluator(instance)
        selected = evaluator.repair(np.ones(instance.n, dtype=np.int8))
        self.assertLessEqual(int(instance.costs[selected].sum()), instance.budget)

    def test_all_unselected_gets_greedy_fill(self) -> None:
        instance = generate_instance("tiny", 30, 79)
        evaluator = Evaluator(instance)
        selected = evaluator.repair(np.zeros(instance.n, dtype=np.int8))
        evaluation = evaluator.evaluate(selected, repair=False)
        self.assertGreater(evaluation.selected_count, 0)
        self.assertTrue(evaluation.feasible)

    def test_evaluation_matches_selected_items(self) -> None:
        instance = generate_instance("tiny", 25, 80)
        evaluator = Evaluator(instance)
        candidate = np.array([1, 0] * 12 + [1], dtype=np.int8)
        evaluation = evaluator.evaluate(candidate)
        self.assertEqual(evaluation.value, int(instance.values[evaluation.selected].sum()))
        self.assertEqual(evaluation.cost, int(instance.costs[evaluation.selected].sum()))
        self.assertLessEqual(evaluation.cost, instance.budget)

    def test_invalid_shape_raises(self) -> None:
        instance = generate_instance("tiny", 10, 81)
        evaluator = Evaluator(instance)
        with self.assertRaises(ValueError):
            evaluator.evaluate(np.zeros(instance.n + 1, dtype=np.int8))


if __name__ == "__main__":
    unittest.main()
