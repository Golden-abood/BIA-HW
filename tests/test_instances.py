from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from config import BUDGET_FRACTION
from src.instance import generate_instance, load_instance, save_instance


class TestInstances(unittest.TestCase):
    def test_generation_is_reproducible(self) -> None:
        first = generate_instance("small", 20, 1001)
        second = generate_instance("small", 20, 1001)
        np.testing.assert_array_equal(first.costs, second.costs)
        np.testing.assert_array_equal(first.values, second.values)
        self.assertEqual(first.budget, second.budget)
        self.assertEqual(first.n, 20)
        self.assertGreater(first.budget, 0)
        self.assertLess(first.budget, first.total_cost)

    def test_budget_fraction(self) -> None:
        instance = generate_instance("medium", 60, 1002)
        expected = int(round(BUDGET_FRACTION * int(instance.costs.sum())))
        self.assertEqual(instance.budget, expected)

    def test_save_and_load_roundtrip(self) -> None:
        instance = generate_instance("large", 150, 1003)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "instance.json"
            save_instance(instance, path)
            loaded = load_instance(path)
        self.assertEqual(instance.name, loaded.name)
        self.assertEqual(instance.n, loaded.n)
        self.assertEqual(instance.budget, loaded.budget)
        self.assertEqual(instance.seed, loaded.seed)
        np.testing.assert_array_equal(instance.costs, loaded.costs)
        np.testing.assert_array_equal(instance.values, loaded.values)


if __name__ == "__main__":
    unittest.main()
