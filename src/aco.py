"""Ant Colony Optimization for the 0/1 knapsack problem."""

from __future__ import annotations

import time

import numpy as np

from config import ACOConfig

from .evaluator import Evaluator
from .instance import ProjectInstance
from .result import RunResult


def run_aco(instance: ProjectInstance, config: ACOConfig, seed: int) -> RunResult:
    if config.max_evaluations < config.colony_size:
        raise ValueError("max_evaluations must be at least the colony size.")

    start = time.perf_counter()
    rng = np.random.default_rng(seed)
    evaluator = Evaluator(instance)
    n = instance.n
    colony_size = config.colony_size

    ratio = instance.values.astype(np.float64) / instance.costs.astype(np.float64)
    eta = ratio / float(np.max(ratio))
    eta_power = np.power(eta, config.beta)

    tau = np.full(n, config.tau0, dtype=np.float64)
    gbest_solution = np.zeros(n, dtype=bool)
    gbest_value = 0
    best_iteration = 0
    history: list[int] = []
    evaluations = 0
    iterations = 0

    while evaluations < config.max_evaluations:
        remaining = config.max_evaluations - evaluations
        batch = min(colony_size, remaining)
        tau_power = np.power(tau, config.alpha)
        score = tau_power * eta_power

        ants = np.zeros((batch, n), dtype=bool)
        ant_fitness = np.zeros(batch, dtype=np.int64)

        for ant in range(batch):
            order = rng.permutation(n)
            random_values = rng.random(n)
            selected = np.zeros(n, dtype=bool)
            load = 0
            for position, item in enumerate(order):
                if load + int(instance.costs[item]) <= instance.budget:
                    if random_values[position] < score[item]:
                        selected[item] = True
                        load += int(instance.costs[item])
            selected = evaluator.repair(selected)
            evaluation = evaluator.evaluate(selected, repair=False)
            ants[ant] = selected
            ant_fitness[ant] = evaluation.value

        evaluations += batch
        iterations += 1

        iteration_best_index = int(np.argmax(ant_fitness))
        iteration_best_value = int(ant_fitness[iteration_best_index])
        iteration_best_solution = ants[iteration_best_index].copy()
        if iteration_best_value > gbest_value:
            gbest_value = iteration_best_value
            gbest_solution = iteration_best_solution.copy()
            best_iteration = iterations

        tau *= 1.0 - config.rho
        if gbest_value > 0:
            tau[gbest_solution] += config.rho * config.global_weight
        if iteration_best_value > 0 and gbest_value > 0:
            quality = iteration_best_value / gbest_value
            tau[iteration_best_solution] += config.rho * config.iteration_weight * quality
        np.clip(tau, config.tau_min, config.tau_max, out=tau)

        history.append(gbest_value)

    best_cost = int(instance.costs[gbest_solution].sum())
    runtime = time.perf_counter() - start
    return RunResult(
        algorithm="ACO",
        best_value=gbest_value,
        best_cost=best_cost,
        best_solution=gbest_solution,
        history=history,
        evaluations=evaluations,
        iterations=iterations,
        best_iteration=best_iteration,
        runtime_sec=runtime,
        seed=seed,
        feasible=best_cost <= instance.budget,
    )
