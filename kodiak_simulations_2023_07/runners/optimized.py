import click
import numpy as np

from typing import Any, Mapping

from .simple import UniswapV3LPSimpleRunner
from ..optimize import find_optimal_delta


# Simple lp runner class that optimizes tick width at each rebalance
class UniswapV3LPOptimizedRunner(UniswapV3LPSimpleRunner):
    mu: float = 0  # GBM drift fit param per block
    sigma: float = 1  # GBM vol fit param per block

    def __init__(self, **data: Any):
        """
        Overrides UniswapV3LPSimpleRunner to check providing either amount0 or amount1.
        """
        super().__init__(**data)

        if self.amount0 == 0 and self.amount1 == 0:
            raise ValueError("self.amounts == 0")

    def _calculate_theta(self, number: int, state: Mapping) -> float:
        """
        Calculates average fee volume per unit of external liquidity
        over last rebalance period.
        """
        tau = self.blocks_between_rebalance
        last_state = self.get_refs_state(number - tau)

        theta0 = (
            (state["fee_growth_global0_x128"] - last_state["fee_growth_global0_x128"]) * state["sqrtPriceX96"]
        ) / (tau * (1 << 224))
        theta1 = (state["fee_growth_global1_x128"] - last_state["fee_growth_global1_x128"]) / (
            tau * state["sqrtPriceX96"] * (1 << 32)
        )
        theta = (theta0 + theta1) / 2
        return theta

    def _optimize_tick_width(self, number: int, state: Mapping):
        """
        Optimizes tick width given latest fee volumes and
        fit mu, sigma stored in runner.
        """
        # @dev only works if self.liquidity << state["liquidity"] since then can "include" in state["liquidity"]
        # TODO: fix for any self.liquidity value
        el = 0
        if self.amount1 != 0:
            el = (self.amount1 * (1 << 96)) / (state["liquidity"] * state["sqrtPriceX96"])
        elif self.amount0 != 0:
            el = (self.amount0 * state["sqrtPriceX96"]) / (state["liquidity"] * (1 << 96))
        else:
            raise "Need amount0, amount1 > 0 to optimize"

        click.echo(f"LP liquidity per unit of external liquidity: {el}")

        fee = self._refs["pool"].fee()  # in bps
        ef = fee / 1e6

        theta = self._calculate_theta(number, state)
        click.echo(f"Fee volume per unit of external liquidity: {theta}")

        (delta, value) = find_optimal_delta(
            self.mu,
            self.sigma,
            self.blocks_between_rebalance,
            ef,
            el,
            theta,
            self._tick_spacing,
        )
        click.echo(f"Optimal delta: {delta}")
        click.echo(f"Expected value at end of next period: {value}")

        # update tick width ensuring multiple of pool tick spacing
        tick_width = int((2 * delta) / np.log(1.0001))
        tick_width = self._tick_spacing * (tick_width // self._tick_spacing)
        click.echo(f"Optimal tick width: {tick_width}")
        self.tick_width = tick_width

    def init_mocks_state(self, number: int, state: Mapping):
        """
        Overrides UniswapV3LPSimpleRunner to optimize tick width prior to
        mock initialization.
        """
        self._optimize_tick_width(number, state)

        # usual mock liquidity provision procedure
        super().init_mocks_state(number, state)

    def update_strategy(self, number: int, state: Mapping):
        """
        Overrides UniswapV3LPSimpleRunner to optimize tick width prior to
        strategy update through backtester contract.
        """
        # only optimize if rebalance period has passed
        if self._block_rebalance_last > 0 and number >= self._block_rebalance_last + self.blocks_between_rebalance:
            self._optimize_tick_width(number, state)

        # usual strategy update procedure
        super().update_strategy(number, state)
