from typing import List
from functools import cmp_to_key, partial
from operator import attrgetter

import numpy as np

from hypernets.utils import logging as hyn_logging
from ..core.pareto import pareto_dominate
from ..core import HyperSpace, Searcher, OptimizeDirection, get_random_state

from .moo import MOOSearcher
from .genetic import Recombination, Individual, SinglePointMutation, Survival

logger = hyn_logging.get_logger(__name__)


class NSGAIndividual(Individual):
    def __init__(self, dna: HyperSpace, scores: np.ndarray, random_state):

        super().__init__(dna, scores, random_state)

        self.dna = dna
        self.scores = scores

        self.rank: int = -1  # rank starts from 1

        self.S: List[NSGAIndividual] = []
        self.n: int = -1

        self.T: List[NSGAIndividual] = []

        self.distance: float = -1.0  # crowding-distance

    def reset(self):
        self.rank = -1
        self.S = []
        self.n = 0
        self.T = []
        self.distance = -1.0

    def __repr__(self):
        return f"(scores={self.scores}, rank={self.rank}, n={self.n}, distance={self.distance})"


class RankAndCrowdSortSurvival(Survival):

    def __init__(self, directions, population_size, random_state):
        self.directions = directions
        self.population_size = population_size
        self.random_state = random_state

    @staticmethod
    def crowding_distance_assignment(I: List[NSGAIndividual]):
        scores_array = np.array([indi.scores for indi in I])

        maximum_array = np.max(scores_array, axis=0)
        minimum_array = np.min(scores_array, axis=0)

        for m in range(len(I[0].scores)):
            sorted_I = list(sorted(I, key=lambda v: v.scores[m], reverse=False))
            sorted_I[0].distance = float("inf")  # so that boundary points always selected, because they are not crowd
            sorted_I[len(I) - 1].distance = float("inf")
            # only assign distances for non-boundary points
            for i in range(1, (len(I) - 1)):
                sorted_I[i].distance = sorted_I[i].distance \
                                       + (sorted_I[i + 1].scores[m] - sorted_I[i - 1].scores[m]) \
                                       / (maximum_array[m] - minimum_array[m])
        return I

    def fast_non_dominated_sort(self, pop: List[NSGAIndividual]):
        for p in pop:
            p.reset()
        directions = self.directions
        F_1 = []
        F = [F_1]  # to store pareto front of levels respectively
        for p in pop:
            p.n = 0
            for q in pop:
                if p == q:
                    continue
                if self.dominate(p, q, pop=pop):
                    p.S.append(q)
                if self.dominate(q, p, pop=pop):
                    p.T.append(q)
                    p.n = p.n + 1

            if p.n == 0:
                p.rank = 0
                F_1.append(p)

        i = 0
        while True:
            Q = []
            for p in F[i]:
                for q in p.S:
                    q.n = q.n - 1
                    if q.n == 0:
                        q.rank = i + 1
                        Q.append(q)
            if len(Q) == 0:
                break
            F.append(Q)
            i = i + 1
        return F

    def sort_font(self, front: List[NSGAIndividual]):
        return self.crowding_distance_assignment(front)

    def sort_population(self, population: List[NSGAIndividual]):
        return sorted(population, key=self.cmp_operator, reverse=False)

    def update(self, pop: List[NSGAIndividual], challengers: List[Individual]):
        temp_pop = []
        temp_pop.extend(pop)
        temp_pop.extend(challengers)
        if len(pop) < self.population_size:
            return temp_pop

        # assign a weighted Euclidean distance for each one
        p_sorted = self.fast_non_dominated_sort(temp_pop)
        if len(p_sorted) == 1 and len(p_sorted[0]) == 0:
            print(f"ERR: {p_sorted}")

        # sort individual in a front
        p_selected: List[NSGAIndividual] = []
        for rank, P_front in enumerate(p_sorted):
            if len(P_front) == 0:
                break
            individuals = self.sort_font(P_front)  # only assign distance for nsga
            p_selected.extend(individuals)
            if len(p_selected) >= self.population_size:
                break

        # ensure population size
        p_cmp_sorted = list(sorted(p_selected, key=cmp_to_key(self.cmp_operator), reverse=True))
        p_final = p_cmp_sorted[:self.population_size]
        logger.debug(f"Individual {p_cmp_sorted[self.population_size-1: ]} have been removed from population,"
                     f" sorted population ={p_cmp_sorted}")

        return p_final

    def dominate(self, ind1: NSGAIndividual, ind2: NSGAIndividual, pop: List[NSGAIndividual]):
        return pareto_dominate(x1=ind1.scores, x2=ind2.scores, directions=self.directions)

    @staticmethod
    def cmp_operator(s1: NSGAIndividual, s2: NSGAIndividual):
        if s1.rank < s2.rank:
            return 1
        elif s1.rank == s2.rank:
            if s1.distance > s2.distance:  # the larger the distance the better
                return 1
            elif s1.distance == s2.distance:
                return 0
            else:
                return -1
        else:
            return -1

    def calc_nondominated_set(self, population: List[NSGAIndividual]):
        def find_non_dominated_solu(indi):
            if (np.array(indi.scores) == None).any():  # illegal individual for the None scores
                return False
            for indi_ in population:
                if indi_ == indi:
                    continue
                if self.dominate(ind1=indi_, ind2=indi, pop=population):
                    return False
            return True  # this is a pareto optimal

        # find non-dominated solution for every solution
        ns = list(filter(lambda s: find_non_dominated_solu(s), population))

        return ns


class NSGAIISearcher(MOOSearcher):
    """An implementation of "NSGA-II".

    References:
        [1]. K. Deb, A. Pratap, S. Agarwal and T. Meyarivan, "A fast and elitist multiobjective genetic algorithm: NSGA-II," in IEEE Transactions on Evolutionary Computation, vol. 6, no. 2, pp. 182-197, April 2002, doi: 10.1109/4235.996017.
    """

    def __init__(self, space_fn, objectives, recombination=None, mutate_probability=0.7,
                 population_size=30, use_meta_learner=False, space_sample_validation_fn=None, random_state=None):

        super().__init__(space_fn=space_fn, objectives=objectives, use_meta_learner=use_meta_learner,
                         space_sample_validation_fn=space_sample_validation_fn)
        self.population: List[NSGAIndividual] = []
        self.random_state = random_state if random_state is not None else get_random_state()
        self.recombination: Recombination = recombination

        self.mutation = SinglePointMutation(self.random_state, mutate_probability)

        self.population_size = population_size

        self.survival = self.create_survival()
        self._historical_individuals: List[NSGAIndividual] = []

    def create_survival(self):
        return RankAndCrowdSortSurvival(directions=self.directions,
                                        population_size=self.population_size,
                                        random_state=self.random_state)

    def binary_tournament_select(self, population):
        indi_inx = self.random_state.randint(low=0, high=len(population) - 1, size=2)  # fixme: maybe duplicated inx

        p1 = population[indi_inx[0]]
        p2 = population[indi_inx[1]]

        # select the first parent
        if self.survival.cmp_operator(p1, p2) >= 0:
            first_inx = indi_inx[0]
        else:
            first_inx = indi_inx[1]

        # select the second parent
        indi_inx = self.random_state.randint(low=0, high=len(population) - 1, size=2)
        try_times = 0
        while first_inx in indi_inx:  # exclude the first individual
            if try_times > 10000:
                raise RuntimeError("too many times for selecting individual to mat. ")
            indi_inx = self.random_state.randint(low=0, high=len(population) - 1, size=2)
            try_times = try_times + 1

        if self.survival.cmp_operator(p1, p2) >= 0:
            second_inx = indi_inx[0]
        else:
            second_inx = indi_inx[1]

        return population[first_inx], population[second_inx]

    @property
    def directions(self):
        return [o.direction for o in self.objectives]

    def sample(self):
        if len(self.population) < self.population_size:
            return self._sample_and_check(self._random_sample)

        # binary tournament selection operation
        p1, p2 = self.binary_tournament_select(self.population)

        try:
            offspring = self.recombination.do(p1, p2, self.space_fn())
            final_offspring = self.mutation.do(offspring.dna, self.space_fn())
        except Exception:
            final_offspring = self.mutation.do(p1.dna, self.space_fn(), proba=1)

        return final_offspring

    def get_best(self):
        return list(map(lambda v: v.dna, self.get_nondominated_set()))

    def update_result(self, space, result):
        indi = NSGAIndividual(space, result, self.random_state)
        self._historical_individuals.append(indi)  # add to history
        p = self.survival.update(pop=self.population,  challengers=[indi])
        self.population = p

        challengers = [indi]

        if challengers[0] in self.population:
            logger.debug(f"new individual{challengers} is accepted by population, current population {self.population}")
        else:
            logger.debug(f"new individual{challengers[0]} is not accepted by population, current population {self.population}")

        # from matplotlib import pyplot as plt
        # self.plot_population()
        # plt.show()

    def get_nondominated_set(self):
        population = self.get_historical_population()
        ns = self.survival.calc_nondominated_set(population)
        return ns

    def get_historical_population(self):
        return self._historical_individuals

    def get_population(self) -> List[Individual]:
        return self.population

    def _sub_plot_pop(self, ax, historical_individuals):
        population = self.get_population()
        not_in_population: List[Individual] = list(filter(lambda v: v not in population, historical_individuals))
        self._do_plot(population, color='red', label='in-population', ax=ax, marker="o")  #
        self._do_plot(not_in_population, color='blue', label='others', ax=ax, marker="o")  # marker="p"
        ax.set_title(f"individual in population(total={len(historical_individuals)}) plot")
        # handles, labels = ax.get_legend_handles_labels()
        objective_names = [_.name for _ in self.objectives]
        ax.set_xlabel(objective_names[0])
        ax.set_ylabel(objective_names[1])
        ax.legend()

    def _sub_plot_ranking(self, ax, historical_individuals):
        p_sorted = self.survival.fast_non_dominated_sort(historical_individuals)
        colors = ['c', 'm', 'y', 'r', 'g']
        n_colors = len(colors)
        for i, front in enumerate(p_sorted[: n_colors]):
            scores = np.array([_.scores for _ in front])
            ax.scatter(scores[:, 0], scores[:, 1], color=colors[i], label=f"rank={i + 1}")

        if len(p_sorted) > n_colors:
            others = []
            for front in p_sorted[n_colors:]:
                others.extend(front)
            scores = np.array([_.scores for _ in others])
            ax.scatter(scores[:, 0], scores[:, 1], color='b', label='others')
        ax.set_title(f"individuals(total={len(historical_individuals)}) ranking plot")
        objective_names = [_.name for _ in self.objectives]
        ax.set_xlabel(objective_names[0])
        ax.set_ylabel(objective_names[1])
        ax.legend()

    def _plot_population(self, figsize=(6, 6), **kwargs):
        from matplotlib import pyplot as plt

        figs, axes = plt.subplots(3, 1, figsize=(figsize[0], figsize[0] * 3))
        historical_individuals = self.get_historical_population()

        # 1. ranking plot
        self._sub_plot_ranking(axes[0], historical_individuals)

        # 2. population plot
        self._sub_plot_pop(axes[1], historical_individuals)

        # 3. dominated plot
        self._plot_pareto(axes[2], historical_individuals)

        return figs, axes

    def reset(self):
        pass

    def export(self):
        pass


class RDominanceSurvival(RankAndCrowdSortSurvival):

    def __init__(self, directions, population_size, random_state, ref_point, weights, threshold):
        super(RDominanceSurvival, self).__init__(directions, population_size=population_size, random_state=random_state)
        self.ref_point = ref_point
        self.weights = weights
        # enables the DM to control the selection pressure of the r-dominance relation.
        self.threshold = threshold

    def dominate(self, ind1: NSGAIndividual, ind2: NSGAIndividual, pop: List[NSGAIndividual], directions=None):

        # check pareto dominate
        if pareto_dominate(ind1.scores, ind2.scores, directions=directions):
            return True

        if pareto_dominate(ind2.scores, ind1.scores, directions=directions):
            return False

        # in case of pareto-equivalent, compare distance
        scores = np.array([_.scores for _ in pop])
        scores_extend = np.max(scores, axis=0) - np.min(scores, axis=0)
        distances = []
        for indi in pop:
            # Calculate weighted Euclidean distance of two solution.
            # Note: if ref_point is infeasible value, distance maybe larger than 1
            indi.distance = np.sqrt(np.sum(np.square((np.asarray(indi.scores) - self.ref_point) / scores_extend) * self.weights))
            distances.append(indi.distance)

        dist_extent = np.max(distances) - np.min(distances)

        return (ind1.distance - ind2.distance) / dist_extent < -self.threshold

    def sort_font(self, front: List[NSGAIndividual]):
        return sorted(front, key=lambda v: v.distance, reverse=False)

    def sort_population(self, population: List[NSGAIndividual]):
        return sorted(population, key=cmp_to_key(self.cmp_operator), reverse=True)

    @staticmethod
    def cmp_operator(s1: NSGAIndividual, s2: NSGAIndividual):
        if s1.rank < s2.rank:
            return 1
        elif s1.rank == s2.rank:
            if s1.distance < s2.distance:  # the smaller the distance the better
                return 1
            elif s1.distance == s2.distance:
                return 0
            else:
                return -1
        else:
            return -1


class RNSGAIISearcher(NSGAIISearcher):
    """An implementation of R-NSGA-II which is a variant of NSGA-II algorithm.

        References:
            [1]. L. Ben Said, S. Bechikh and K. Ghedira, "The r-Dominance: A New Dominance Relation for Interactive Evolutionary Multicriteria Decision Making," in IEEE Transactions on Evolutionary Computation, vol. 14, no. 5, pp. 801-818, Oct. 2010, doi: 10.1109/TEVC.2010.2041060.
    """
    def __init__(self, space_fn, objectives, ref_point=None, weights=None, dominance_threshold=0.3,
                 recombination=None, mutate_probability=0.7, population_size=30, use_meta_learner=False,
                 space_sample_validation_fn=None, random_state=None):
        """
        Parameters
        ----------
        ref_point: Tuple[float], required
            user-specified reference point, used to guide the search toward the desired region.

        weights:  Tuple[float], optional, default to uniform
            weights vector, provides more detailed information about what Pareto optimal to converge to.

        dominance_threshold: float, optional, default to 0.3
            distance threshold, in case of pareto-equivalent, compare distance between two solutions.
        """

        n_objectives = len(objectives)

        self.ref_point = ref_point if ref_point is not None else [0.0] * n_objectives
        self.weights = weights if weights is not None else [1 / n_objectives] * n_objectives
        self.dominance_threshold = dominance_threshold

        super(RNSGAIISearcher, self).__init__(space_fn=space_fn, objectives=objectives, recombination=recombination,
                                              mutate_probability=mutate_probability, population_size=population_size,
                                              use_meta_learner=use_meta_learner,
                                              space_sample_validation_fn=space_sample_validation_fn,
                                              random_state=random_state)

    def create_survival(self):
        return RDominanceSurvival(random_state=self.random_state,
                                  population_size=self.population_size,
                                  ref_point=self.ref_point,
                                  weights=self.weights, threshold=self.dominance_threshold,
                                  directions=self.directions)

    def _plot_population(self, figsize=(6, 6), show_ref_point=True, show_weights=False, **kwargs):
        from matplotlib import pyplot as plt

        def attach(ax):
            if show_ref_point:
                ref_point = self.ref_point
                ax.scatter([ref_point[0]], [ref_point[1]], c='green', marker="*", label='ref point')
            if show_weights:
                weights = self.weights
                # plot a vector
                ax.quiver(0, 0, weights[0], weights[1], angles='xy', scale_units='xy', label='weights')

        n_axes = 4
        figs, axes = plt.subplots(2, 2, figsize=(figsize[0] * 2, figsize[0] * 2))
        historical_individuals = self.get_historical_population()

        # 1. ranking plot
        ax1 = axes[0][0]
        self._sub_plot_ranking(ax1, historical_individuals)
        attach(ax1)

        # 2. population plot
        ax2 = axes[0][1]
        self._sub_plot_pop(ax2, historical_individuals)
        attach(ax2)

        # 3. r-dominated plot
        ax3 = axes[1][0]
        n_set = self.get_nondominated_set()
        d_set: List[Individual] = list(filter(lambda v: v not in n_set, historical_individuals))
        self._do_plot(n_set, color='red', label='non-dominated', ax=ax3, marker="o")  # , marker="o"
        self._do_plot(d_set, color='blue', label='dominated', ax=ax3, marker="o")
        ax3.set_title(f"non-dominated solution (total={len(historical_individuals)}) in R-dominance scene")
        objective_names = [_.name for _ in self.objectives]
        ax3.set_xlabel(objective_names[0])
        ax3.set_ylabel(objective_names[1])
        ax3.legend()
        attach(ax3)

        # 4. pareto dominated plot
        ax4 = axes[1][1]
        self._plot_pareto(ax4, historical_individuals)
        attach(ax4)



        return figs, axes

