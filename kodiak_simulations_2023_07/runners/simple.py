import click

from typing import ClassVar, Mapping

from .base import UniswapV3LPFixedWidthRunner
from ..utils import (
    get_amounts_for_liquidity,
    get_liquidity_for_amounts,
    get_liquidity_for_amount0,
    get_liquidity_for_amount1,
    get_sqrt_ratio_at_tick,
)


# fixed tick width lp runner class for simple backtesting
class UniswapV3LPSimpleRunner(UniswapV3LPFixedWidthRunner):
    _backtester_name: ClassVar[str] = "UniswapV3LPSimpleBacktest"

    def _calculate_position_liquidity(self, state: Mapping) -> int:
        """
        Calculate the liquidity backing the position.

        Args:
            state (Mapping): The state of mocks
        """
        # WARNING: pool liquidity in mock_pool *includes* this amount
        return get_liquidity_for_amounts(
            state["slot0"].sqrtPriceX96,  # sqrt_ratio_x96
            get_sqrt_ratio_at_tick(self.tick_lower),  # sqrt_ratio_a_x96
            get_sqrt_ratio_at_tick(self.tick_upper),  # sqrt_ratio_b_x96,
            self.amount0,
            self.amount1,
        )

    def init_mocks_state(self, number: int, state: Mapping):
        """
        Overrides UniswapV3LPRunner to use tick width and store liquidity contribution by LP.

        Args:
            number (int): The block number at init.
            state (Mapping): The init state of mocks.
        """
        mock_pool = self._mocks["pool"]

        # some setup based off initial state
        tick_lower, tick_upper = self._calculate_lp_ticks(state)
        self.tick_lower = tick_lower
        self.tick_upper = tick_upper

        # calc missing attrs based on input given
        if self.liquidity != 0:
            (amount0_desired, amount1_desired) = get_amounts_for_liquidity(
                state["slot0"].sqrtPriceX96,  # sqrt_ratio_x96
                get_sqrt_ratio_at_tick(self.tick_lower),  # sqrt_ratio_a_x96
                get_sqrt_ratio_at_tick(self.tick_upper),  # sqrt_ratio_b_x96
                self.liquidity,
            )
            self.amount0 = amount0_desired
            self.amount1 = amount1_desired
        elif self.amount0 != 0 and self.amount1 == 0:
            liquidity = get_liquidity_for_amount0(
                state["slot0"].sqrtPriceX96,
                get_sqrt_ratio_at_tick(self.tick_upper),
                self.amount0,
            )
            (_, amount1_desired) = get_amounts_for_liquidity(
                state["slot0"].sqrtPriceX96,  # sqrt_ratio_x96
                get_sqrt_ratio_at_tick(self.tick_lower),  # sqrt_ratio_a_x96
                get_sqrt_ratio_at_tick(self.tick_upper),  # sqrt_ratio_b_x96
                liquidity,
            )
            self.liquidity = liquidity
            self.amount1 = amount1_desired
        elif self.amount1 != 0 and self.amount0 == 0:
            liquidity = get_liquidity_for_amount1(
                get_sqrt_ratio_at_tick(self.tick_lower),
                state["slot0"].sqrtPriceX96,
                self.amount1,
            )
            (amount0_desired, _) = get_amounts_for_liquidity(
                state["slot0"].sqrtPriceX96,  # sqrt_ratio_x96
                get_sqrt_ratio_at_tick(self.tick_lower),  # sqrt_ratio_a_x96
                get_sqrt_ratio_at_tick(self.tick_upper),  # sqrt_ratio_b_x96
                liquidity,
            )
            self.liquidity = liquidity
            self.amount0 = amount0_desired

        click.echo(f"Runner liquidity: {self.liquidity}")
        click.echo(f"Runner amounts: {(self.amount0, self.amount1)}")

        # reset ref state fetch given ticks stored
        state = self.get_refs_state(number)

        # set the tick for position manager add liquidity to work properly
        self.set_mocks_state(state)

        # establish position attributes on backtester contract
        self.backtester.update(mock_pool.address, self.tick_lower, self.tick_upper, self.liquidity, sender=self.acc)

        click.echo("Backtester position attributes ...")
        click.echo(f"ticks: {(self.backtester.tickLower_(), self.backtester.tickUpper_())}")
        click.echo(
            f"feeGrowthInside: {(self.backtester.feeGrowthInside0X128_(), self.backtester.feeGrowthInside1X128_())}"
        )
        click.echo(f"liquidity: {self.backtester.liquidity_()}")

        # set block as processed
        self._last_number_processed = number

    def update_strategy(self, number: int, state: Mapping):
        """
        Updates the strategy being backtested through backtester contract.

        Rebalances symmetrically around current tick, with
          - tick_lower = tick_current - tick_width // 2
          - tick_upper = tick_current + tick_width // 2
        """
        # set block as processed
        self._last_number_processed = number

        if self._block_rebalance_last == 0:
            self._block_rebalance_last = number
            return
        elif number < self._block_rebalance_last + self.blocks_between_rebalance:
            return

        # TODO: implement with rebalance logic and compounding fees if specified
        click.echo("Rebalancing LP position ...")
