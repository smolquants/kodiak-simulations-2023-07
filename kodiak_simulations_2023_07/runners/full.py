from typing import ClassVar, Mapping

from backtest_ape.uniswap.v3.lp.mgmt import mint_lp_position
from backtest_ape.uniswap.v3.lp.setup import approve_mock_tokens, mint_mock_tokens

from .base import UniswapV3LPFixedWidthRunner
from ..utils import (
    get_sqrt_ratio_at_tick,
    get_amounts_for_liquidity,
    get_liquidity_for_amount0,
    get_liquidity_for_amount1,
)


# fixed tick width lp runner class for full backtesting
class UniswapV3LPFullRunner(UniswapV3LPFixedWidthRunner):
    _backtester_name: ClassVar[str] = "UniswapV3LPFullBacktest"

    def _get_position_liquidity(self, token_id: int) -> int:
        """
        Gets the liquidity backing the position associated with the given token id.

        Args:
            token_id (int): Token ID of the LP position
        """
        manager = self._mocks["manager"]
        (_, _, _, _, _, _, _, liquidity, _, _, _, _) = manager.positions(token_id)
        return liquidity

    def init_mocks_state(self, number: int, state: Mapping):
        """
        Overrides UniswapV3LPRunner to use tick width and store liquidity contribution by LP.

        Args:
            number (int): The block number at init.
            state (Mapping): The init state of mocks.
        """
        mock_tokens = self._mocks["tokens"]
        mock_manager = self._mocks["manager"]
        mock_pool = self._mocks["pool"]

        # TODO: check whether issue minting on manager with fee accounting after set mock state
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

        # reset ref state fetch given ticks stored
        state = self.get_refs_state(number)

        # set the tick for position manager add liquidity to work properly
        self.set_mocks_state(state)

        # approve manager for infinite spend on mock tokens
        approve_mock_tokens(
            mock_tokens,
            self.backtester,
            mock_manager,
            self.acc,
        )

        # mint both tokens to backtester
        mint_mock_tokens(
            mock_tokens,
            self.backtester,
            [self.amount0 * 1000, self.amount1 * 1000],  # mint more tokens than needed
            self.acc,
        )

        # then mint the LP position
        mint_lp_position(
            mock_manager,
            mock_pool,
            self.backtester,
            [self.tick_lower, self.tick_upper],
            [self.amount0, self.amount1],
            self.acc,
        )
        token_id = self.backtester.count() + 1
        self._token_id = token_id

        # store token id in backtester
        self.backtester.push(token_id, sender=self.acc)

        # set block as processed
        self._last_number_processed = number  # TODO: move to set_mocks_state(number, state)

        # store the actual liquidity minted
        self.liquidity = self._get_position_liquidity(self._token_id)

    def update_strategy(self, number: int, state: Mapping):
        """
        Updates the strategy being backtested through backtester contract.

        Rebalances symmetrically around current tick, with
          - tick_lower = tick_current - tick_width // 2
          - tick_upper = tick_current + tick_width // 2
        """
        # set block as processed
        self._last_number_processed = number  # TODO: move to set_mocks_state(number, state)

        if self._block_rebalance_last == 0:
            self._block_rebalance_last = number
            return
        elif number < self._block_rebalance_last + self.blocks_between_rebalance:
            return

        # TODO: implement
