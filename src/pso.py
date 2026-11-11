"""Binary Particle Swarm Optimization for the 0/1 knapsack problem."""

from __future__ import annotations

import time

import numpy as np

from config import BPSOConfig

from .evaluator import Evaluator
from .instance import ProjectInstance
from .result import RunResult


def _evaluate_swarm(
    positions: np.ndarray, evaluator: Evaluator
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    count = positions.shape[0]
    repaired = np.empty((count, evaluator.n), dtype=bool)
    fitness = np.empty(count, dtype=np.int64)
    costs = np.empty(count, dtype=np.int64)
    for index in range(count):
        evaluation = evaluator.evaluate(positions[index], repair=True)
        repaired[index] = evaluation.selected
        fitness[index] = evaluation.value
        costs[index] = evaluation.cost
    return repaired, fitness, costs


def run_bpso(instance: ProjectInstance, config: BPSOConfig, seed: int) -> RunResult:
    if config.max_evaluations < config.swarm_size:
        raise ValueError("max_evaluations must be at least the swarm size.")

    start = time.perf_counter()
    rng = np.random.default_rng(seed)
    evaluator = Evaluator(instance)
    n = instance.n
    swarm_size = config.swarm_size

    positions = (rng.random((swarm_size, n)) < 0.5).astype(np.int8)
    velocities = rng.uniform(-1.0, 1.0, size=(swarm_size, n))
    repaired, fitness, _ = _evaluate_swarm(positions, evaluator)
    positions = repaired.astype(np.int8)
    evaluations = swarm_size

    pbest_positions = positions.copy()
    pbest_fitness = fitness.copy()
    gbest_index = int(np.argmax(pbest_fitness))
    gbest_solution = pbest_positions[gbest_index].astype(bool).copy()
    gbest_value = int(pbest_fitness[gbest_index])
    best_iteration = 0
    history = [gbest_value]
    iterations = 0

    while evaluations < config.max_evaluations:
        remaining = config.max_evaluations - evaluations
        batch = min(swarm_size, remaining)
        progress = evaluations / config.max_evaluations
        inertia = config.inertia_start + (config.inertia_end - config.inertia_start) * progress

        r1 = rng.random((batch, n))
        r2 = rng.random((batch, n))
        active_velocity = velocities[:batch]
        active_positions = positions[:batch]
        active_pbest = pbest_positions[:batch]

        active_velocity = (
            inertia * active_velocity
            + config.c1 * r1 * (active_pbest - active_positions)
            + config.c2 * r2 * (gbest_solution.astype(np.int8) - active_positions)
        )
        active_velocity = np.clip(active_velocity, -config.vmax, config.vmax)
        velocities[:batch] = active_velocity

        probabilities = 1.0 / (1.0 + np.exp(-active_velocity))
        new_positions = (rng.random((batch, n)) < probabilities).astype(np.int8)
        repaired, fitness, _ = _evaluate_swarm(new_positions, evaluator)
        evaluations += batch
        iterations += 1

        positions[:batch] = repaired.astype(np.int8)
        better = fitness > pbest_fitness[:batch]
        if np.any(better):
            pbest_positions[:batch][better] = positions[:batch][better]
            pbest_fitness[:batch][better] = fitness[better]

        iteration_best_index = int(np.argmax(fitness))
        iteration_best_value = int(fitness[iteration_best_index])
        if iteration_best_value > gbest_value:
            gbest_value = iteration_best_value
            gbest_solution = repaired[iteration_best_index].astype(bool).copy()
            best_iteration = iterations

        history.append(gbest_value)

    best_cost = int(instance.costs[gbest_solution].sum())
    runtime = time.perf_counter() - start
    return RunResult(
        algorithm="BPSO",
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
