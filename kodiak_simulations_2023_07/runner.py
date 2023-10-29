import os
import pandas as pd

from typing import Any, ClassVar, List, Mapping

from backtest_ape.uniswap.v3 import UniswapV3LPBaseRunner
from backtest_ape.uniswap.v3.lp.mgmt import mint_lp_position
from backtest_ape.uniswap.v3.lp.setup import approve_mock_tokens, mint_mock_tokens

from .utils import (
    get_sqrt_ratio_at_tick,
    get_amounts_for_liquidity,
    get_liquidity_for_amount0,
    get_liquidity_for_amount1,
)


# fixed tick width lp runner classes for backtesting
class UniswapV3LPFixedWidthRunner(UniswapV3LPBaseRunner):
    liquidity: int = 0  # liquidity contribution by LP
    tick_width: int = 0  # 2 * delta
    blocks_between_rebalance: int = 0  # blocks between rebalances (assumes fixed blocktimes)

    _token_id: int = 1  # current token id
    _block_rebalance_last: int = 0  # last block rebalanced
    _backtester_name: ClassVar[str] = "UniswapV3LPFullBacktest"
    _tick_spacing: int = 0
    _last_number_processed: int = 0

    def __init__(self, **data: Any):
        """
        Overrides UniswapV3LPRunner to check tick width // 2 is a multiple of pool
        tick spacing.
        """
        super().__init__(**data)

        if self.liquidity == 0 and (self.amount0 == 0 and self.amount1 == 0):
            raise ValueError("both self.liquidity and self.amounts == 0")

        pool = self._refs["pool"]
        self._tick_spacing = pool.tickSpacing()
        if (self.tick_width // 2) % self._tick_spacing != 0:
            raise ValueError("self.tick_width // 2 not a multiple of pool.tickSpacing")

    def _get_position_liquidity(self, token_id: int) -> int:
        """
        Gets the liquidity backing the position associated with the given token id.

        Args:
            token_id (int): Token ID of the LP position
        """
        manager = self._mocks["manager"]
        (_, _, _, _, _, _, _, liquidity, _, _, _, _) = manager.positions(token_id)
        return liquidity

    def _calculate_lp_ticks(self, state: Mapping) -> (int, int):
        """
        Calculates anticipated tick upper and lower with fixed width around
        current tick.

        Args:
            state (Mapping): The state of mocks.
        """
        # get the closest available liquidity tick
        remainder = state["slot0"].tick % self._tick_spacing
        tick = (
            state["slot0"].tick - remainder
            if remainder < self._tick_spacing // 2
            else state["slot0"].tick + (self._tick_spacing - remainder)
        )

        # fixed width straddles closest tick to current state
        tick_lower = tick - self.tick_width // 2
        tick_upper = tick + self.tick_width // 2
        return (tick_lower, tick_upper)

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
                get_sqrt_ratio_at_tick(state["slot0"].tick),  # sqrt_ratio_x96
                get_sqrt_ratio_at_tick(self.tick_lower),  # sqrt_ratio_a_x96
                get_sqrt_ratio_at_tick(self.tick_upper),  # sqrt_ratio_b_x96
                self.liquidity,
            )
            self.amount0 = amount0_desired
            self.amount1 = amount1_desired
        elif self.amount0 != 0 and self.amount1 == 0:
            liquidity = get_liquidity_for_amount0(
                get_sqrt_ratio_at_tick(state["slot0"].tick),
                get_sqrt_ratio_at_tick(self.tick_upper),
                self.amount0,
            )
            (_, amount1_desired) = get_amounts_for_liquidity(
                get_sqrt_ratio_at_tick(state["slot0"].tick),  # sqrt_ratio_x96
                get_sqrt_ratio_at_tick(self.tick_lower),  # sqrt_ratio_a_x96
                get_sqrt_ratio_at_tick(self.tick_upper),  # sqrt_ratio_b_x96
                liquidity,
            )
            self.liquidity = liquidity
            self.amount1 = amount1_desired
        elif self.amount1 != 0 and self.amount0 == 0:
            liquidity = get_liquidity_for_amount1(
                get_sqrt_ratio_at_tick(self.tick_lower),
                get_sqrt_ratio_at_tick(state["slot0"].tick),
                self.amount1,
            )
            (amount0_desired, _) = get_amounts_for_liquidity(
                get_sqrt_ratio_at_tick(state["slot0"].tick),  # sqrt_ratio_x96
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

        # store token id in backtester
        self.backtester.push(token_id, sender=self.acc)

        # set block as processed
        self._last_number_processed = number  # TODO: move to set_mocks_state(number, state)

        # store the actual liquidity minted
        self.liquidity = self._get_position_liquidity(self._token_id)

    def _get_mocks_state(self) -> Mapping:
        """
        Gets current state of mocks.

        Returns:
            Mapping: The current state of mocks.
        """
        mock_pool = self._mocks["pool"]
        state = {}

        state["slot0"] = mock_pool.slot0()
        state["liquidity"] = mock_pool.liquidity()
        state["fee_growth_global0_x128"] = mock_pool.feeGrowthGlobal0X128()
        state["fee_growth_global1_x128"] = mock_pool.feeGrowthGlobal1X128()
        state["tick_info_lower"] = mock_pool.ticks(self.tick_lower)
        state["tick_info_upper"] = mock_pool.ticks(self.tick_upper)

        return state

    def set_mocks_state(self, state: Mapping):
        """
        Overrides UniswapV3LPRunner to set based off deltas from prior ref state.

        Args:
            TODO: number (int): The block number of current iteration.
            state (Mapping): The ref state at given block iteration.
        """
        mock_pool = self._mocks["pool"]

        datas = []
        if self._last_number_processed == 0:
            # initialize with current state and not deltas
            datas = [
                mock_pool.setSqrtPriceX96.as_transaction(state["slot0"].sqrtPriceX96).data,
                mock_pool.setLiquidity.as_transaction(state["liquidity"]).data,
                mock_pool.setFeeGrowthGlobalX128.as_transaction(
                    state["fee_growth_global0_x128"], state["fee_growth_global1_x128"]
                ).data,
                mock_pool.setTicks.as_transaction(
                    self.tick_lower,
                    state["tick_info_lower"].liquidityGross,
                    state["tick_info_lower"].liquidityNet,
                    state["tick_info_lower"].feeGrowthOutside0X128,
                    state["tick_info_lower"].feeGrowthOutside1X128,
                ).data,
                mock_pool.setTicks.as_transaction(
                    self.tick_upper,
                    state["tick_info_upper"].liquidityGross,
                    state["tick_info_upper"].liquidityNet,
                    state["tick_info_upper"].feeGrowthOutside0X128,
                    state["tick_info_upper"].feeGrowthOutside1X128,
                ).data,
            ]
        else:
            # set with deltas from prior ref state
            prior_state = self.get_refs_state(self._last_number_processed)
            keys = ["liquidity", "fee_growth_global0_x128", "fee_growth_global1_x128"]
            deltas = {k: state[k] - prior_state[k] for k in keys}

            # go one level deeper for tick info keys to delta
            infos = ["tick_info_lower", "tick_info_upper"]
            attrs = ["liquidityGross", "liquidityNet", "feeGrowthOutside0X128", "feeGrowthOutside1X128"]
            deltas.update({i: {a: getattr(state[i], a) - getattr(prior_state[i], a) for a in attrs} for i in infos})

            # get current mock state for items would like to add delta to
            mocks_state = self._get_mocks_state()

            datas = [
                mock_pool.setSqrtPriceX96.as_transaction(state["slot0"].sqrtPriceX96).data,
                mock_pool.setLiquidity.as_transaction(mocks_state["liquidity"] + deltas["liquidity"]).data,
                mock_pool.setFeeGrowthGlobalX128.as_transaction(
                    mocks_state["fee_growth_global0_x128"] + deltas["fee_growth_global0_x128"],
                    mocks_state["fee_growth_global1_x128"] + deltas["fee_growth_global1_x128"],
                ).data,
                mock_pool.setTicks.as_transaction(
                    self.tick_lower,
                    mocks_state["tick_info_lower"].liquidityGross + deltas["tick_info_lower"]["liquidityGross"],
                    mocks_state["tick_info_lower"].liquidityNet + deltas["tick_info_lower"]["liquidityNet"],
                    mocks_state["tick_info_lower"].feeGrowthOutside0X128
                    + deltas["tick_info_lower"]["feeGrowthOutside0X128"],
                    mocks_state["tick_info_lower"].feeGrowthOutside1X128
                    + deltas["tick_info_lower"]["feeGrowthOutside1X128"],
                ).data,
                mock_pool.setTicks.as_transaction(
                    self.tick_upper,
                    mocks_state["tick_info_upper"].liquidityGross + deltas["tick_info_upper"]["liquidityGross"],
                    mocks_state["tick_info_upper"].liquidityNet + deltas["tick_info_upper"]["liquidityNet"],
                    mocks_state["tick_info_upper"].feeGrowthOutside0X128
                    + deltas["tick_info_upper"]["feeGrowthOutside0X128"],
                    mocks_state["tick_info_upper"].feeGrowthOutside1X128
                    + deltas["tick_info_upper"]["feeGrowthOutside1X128"],
                ).data,
            ]

        mock_pool.calls(datas, sender=self.acc)

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

        # TODO: implement for remove liquidity then rebalance swap ...

    def record(self, path: str, number: int, state: Mapping, values: List[int]):
        """
        Overwrites UniswapV3LPRunner to record the value, some state at the given block,
        and liquidity + amounts backing LP's position.

        Args:
            path (str): The path to the csv file to write the record to.
            number (int): The block number.
            state (Mapping): The state of references at block number.
            values (List[int]): The values of the backtester for the state.
        """
        data = {"number": number}
        for i, value in enumerate(values):
            data[f"values{i}"] = value

        data.update(
            {
                "sqrtPriceX96": state["slot0"].sqrtPriceX96,
                "tick": state["slot0"].tick,
                "liquidity": state["liquidity"],
                "position_token_id": self._token_id,
                "position_liquidity": self.liquidity,
                "position_tick_lower": self.tick_lower,
                "position_tick_upper": self.tick_upper,
                "position_amount0": self.amount0,
                "position_amount1": self.amount1,
            }
        )

        header = not os.path.exists(path)
        df = pd.DataFrame(data={k: [v] for k, v in data.items()})
        df.to_csv(path, index=False, mode="a", header=header)
