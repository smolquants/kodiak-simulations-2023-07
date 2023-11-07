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


# Fixed tick width lp runner class for simple backtesting
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

    def _calculate_position_amounts_after_rebalance(
        self, state: Mapping, amount0_before: int, amount1_before: int
    ) -> (int, int):
        """
        Calculate position amounts to rebalance to.

        Rebalance condition: price * amount0 == amount1

        Args:
            state (Mapping): The state of mocks
        """
        liquidity = state["liquidity"]
        price = (int(state["slot0"].sqrtPriceX96) ** 2) // (1 << 192)
        value1 = amount0_before * price + amount1_before
        x1 = (liquidity * state["slot0"].sqrtPriceX96) // (1 << 96)

        amount1 = value1 // 2  # (1/2) * (dx * p + dy)
        dx1 = amount1 - amount1_before  # (1/2) * |dx * p - dy|
        if dx1 == 0:
            return (amount0_before, amount1_before)

        # correct for fee and second order slippage terms
        fee = self._refs["pool"].fee()  # in bps
        _f = fee / 1e6
        eps1 = int(-abs(dx1) * (_f / 2 + (1 / 2) * abs(dx1) / x1))

        amount1 += eps1
        amount0 = amount1 // price  # satisfies rebalance condition

        click.echo("Calculating position amounts after rebalance ...")
        click.echo(f"Amounts (before): {(amount0_before, amount1_before)}")
        click.echo(f"Amounts (after): {(amount0, amount1)}")
        click.echo(f"Value (before): {value1}")
        click.echo(f"Value (after): {amount0 * price + amount1}")

        return (amount0, amount1)

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

    def set_mocks_state(self, state: Mapping):
        """
        Overrides UniswapV3LPFixedWidthRunner to also refresh backtester LP
        in case ref lower or upper tick has been initialized since last block
        processed.

        Args:
            state (Mapping): The ref state at given block iteration.
        """
        super().set_mocks_state(state)

        # TODO: fix so doesn't disregard fees by finding block which ref tick flipped
        if self._last_number_processed != 0:
            last_state = self.get_refs_state(self._last_number_processed)

            # "refresh" LP position if one of the ref ticks has been initialized since last block processed
            lower_changed = (not last_state["tick_info_lower"].initialized) and state["tick_info_lower"].initialized
            upper_changed = (not last_state["tick_info_upper"].initialized) and state["tick_info_upper"].initialized

            click.echo(f"Tick lower initialized state changed?: {lower_changed}")
            click.echo(f"Tick upper initialized state changed?: {upper_changed}")

            if lower_changed or upper_changed:
                mock_pool = self._mocks["pool"]
                self.backtester.update(
                    mock_pool.address, self.tick_lower, self.tick_upper, self.liquidity, sender=self.acc
                )

    def update_strategy(self, number: int, state: Mapping):
        """
        Updates the strategy being backtested through backtester contract.

        Rebalances symmetrically around current tick, with
          - tick_lower = tick_current - tick_width // 2
          - tick_upper = tick_current + tick_width // 2
        """
        # reset block processed number
        self._last_number_processed = 0

        if self._block_rebalance_last == 0:
            self._block_rebalance_last = number
            self._last_number_processed = number
            return
        elif number < self._block_rebalance_last + self.blocks_between_rebalance:
            self._last_number_processed = number
            return

        # calculate new tick range to rebalance around
        # @dev simply keep passively LPing if tick range same and no compounding of fees
        tick_lower, tick_upper = self._calculate_lp_ticks(state)
        if self.tick_lower == tick_lower and self.tick_upper == tick_upper and not self.compound_fees_at_rebalance:
            self._last_number_processed = number
            return

        self.tick_lower = tick_lower
        self.tick_upper = tick_upper

        click.echo(f"Rebalancing LP position at block {number} ...")
        (amount0, amount1) = self.backtester.principal(state["slot0"].sqrtPriceX96)
        (fees0, fees1) = self.backtester.fees()

        # add to runner stored cumulative fees
        self._fees0_cumulative += fees0
        self._fees1_cumulative += fees1

        # add fees to principal amounts if compound at rebalance
        if self.compound_fees_at_rebalance:
            amount0 += fees0
            amount1 += fees1

        (amount0, amount1) = self._calculate_position_amounts_after_rebalance(state, amount0, amount1)
        self.amount0 = amount0
        self.amount1 = amount1

        # @dev must recalculate liquidity *after* set rebalanced amounts and new upper, lower ticks
        self.liquidity = self._calculate_position_liquidity(state)

        click.echo(f"Runner liquidity: {self.liquidity}")
        click.echo(f"Runner amounts: {(self.amount0, self.amount1)}")

        # reset ref state fetch given ticks stored
        state = self.get_refs_state(number)

        # set the tick for position manager add liquidity to work properly
        self.set_mocks_state(state)

        # establish position attributes on backtester contract
        mock_pool = self._mocks["pool"]
        self.backtester.update(mock_pool.address, self.tick_lower, self.tick_upper, self.liquidity, sender=self.acc)

        click.echo("Backtester position attributes ...")
        click.echo(f"ticks: {(self.backtester.tickLower_(), self.backtester.tickUpper_())}")
        click.echo(
            f"feeGrowthInside: {(self.backtester.feeGrowthInside0X128_(), self.backtester.feeGrowthInside1X128_())}"
        )
        click.echo(f"liquidity: {self.backtester.liquidity_()}")

        # check fee values reset
        click.echo(f"values: {self.backtester.values()}")

        # set position as rebalanced
        self._block_rebalance_last = number
        self._last_number_processed = number
