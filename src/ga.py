"""Genetic Algorithm for the 0/1 knapsack problem."""

from __future__ import annotations

import time

import numpy as np

from config import GAConfig

from .evaluator import Evaluator
from .instance import ProjectInstance
from .result import RunResult


def _evaluate_batch(
    candidates: np.ndarray, evaluator: Evaluator
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    count = candidates.shape[0]
    selected = np.empty((count, evaluator.n), dtype=bool)
    fitness = np.empty(count, dtype=np.int64)
    costs = np.empty(count, dtype=np.int64)
    for index in range(count):
        evaluation = evaluator.evaluate(candidates[index], repair=True)
        selected[index] = evaluation.selected
        fitness[index] = evaluation.value
        costs[index] = evaluation.cost
    return selected, fitness, costs


def _tournament(fitness: np.ndarray, rng: np.random.Generator, k: int, count: int) -> np.ndarray:
    population_size = fitness.size
    contestants = rng.integers(0, population_size, size=(count, k))
    winners = np.argmax(fitness[contestants], axis=1)
    return contestants[np.arange(count), winners]


def _elitist_selection(
    parents: np.ndarray,
    parent_fitness: np.ndarray,
    children: np.ndarray,
    child_fitness: np.ndarray,
    population_size: int,
    elitism: int,
) -> tuple[np.ndarray, np.ndarray]:
    elitism = min(elitism, population_size)
    parent_order = np.argsort(-parent_fitness, kind="stable")
    elite_indices = parent_order[:elitism]
    selected = [parents[index] for index in elite_indices]
    selected_fitness = [parent_fitness[index] for index in elite_indices]

    pool = np.vstack([parents[parent_order[elitism:]], children])
    pool_fitness = np.concatenate([parent_fitness[parent_order[elitism:]], child_fitness])
    pool_order = np.argsort(-pool_fitness, kind="stable")
    needed = population_size - len(selected)
    for index in pool_order[:needed]:
        selected.append(pool[index])
        selected_fitness.append(pool_fitness[index])

    return np.asarray(selected, dtype=np.int8), np.asarray(selected_fitness, dtype=np.int64)


def run_ga(instance: ProjectInstance, config: GAConfig, seed: int) -> RunResult:
    if config.max_evaluations < config.population_size:
        raise ValueError("max_evaluations must be at least the population size.")

    start = time.perf_counter()
    rng = np.random.default_rng(seed)
    evaluator = Evaluator(instance)
    n = instance.n
    population_size = config.population_size
    mutation_prob = config.mutation_prob if config.mutation_prob is not None else 1.0 / n

    population = (rng.random((population_size, n)) < 0.5).astype(np.int8)
    population, fitness, _ = _evaluate_batch(population, evaluator)
    population = population.astype(np.int8)
    evaluations = population_size

    best_index = int(np.argmax(fitness))
    best_solution = population[best_index].astype(bool).copy()
    best_value = int(fitness[best_index])
    best_iteration = 0
    history = [best_value]
    iterations = 0

    while evaluations < config.max_evaluations:
        remaining = config.max_evaluations - evaluations
        batch = min(population_size, remaining)

        parent_one = _tournament(fitness, rng, config.tournament_size, batch)
        parent_two = _tournament(fitness, rng, config.tournament_size, batch)
        children = population[parent_one].copy()
        crossover_mask = rng.random((batch, n)) < 0.5
        crossed = np.where(crossover_mask, population[parent_one], population[parent_two])
        do_crossover = rng.random(batch) < config.crossover_prob
        children[do_crossover] = crossed[do_crossover]
        mutation_mask = rng.random((batch, n)) < mutation_prob
        children ^= mutation_mask.astype(np.int8)

        children, child_fitness, _ = _evaluate_batch(children, evaluator)
        children = children.astype(np.int8)
        evaluations += batch
        iterations += 1

        population, fitness = _elitist_selection(
            population,
            fitness,
            children,
            child_fitness,
            population_size,
            config.elitism,
        )

        generation_best_index = int(np.argmax(fitness))
        generation_best_value = int(fitness[generation_best_index])
        if generation_best_value > best_value:
            best_value = generation_best_value
            best_solution = population[generation_best_index].astype(bool).copy()
            best_iteration = iterations
        history.append(best_value)

    best_cost = int(instance.costs[best_solution].sum())
    runtime = time.perf_counter() - start
    return RunResult(
        algorithm="GA",
        best_value=best_value,
        best_cost=best_cost,
        best_solution=best_solution,
        history=history,
        evaluations=evaluations,
        iterations=iterations,
        best_iteration=best_iteration,
        runtime_sec=runtime,
        seed=seed,
        feasible=best_cost <= instance.budget,
    )
