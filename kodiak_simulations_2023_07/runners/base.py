import os
import pandas as pd

from typing import Any, List, Mapping

from backtest_ape.uniswap.v3 import UniswapV3LPBaseRunner


# fixed tick width lp runner classes for backtesting
class UniswapV3LPFixedWidthRunner(UniswapV3LPBaseRunner):
    liquidity: int = 0  # liquidity contribution by LP
    tick_width: int = 0  # 2 * delta
    blocks_between_rebalance: int = 0  # tau
    compound_fees_at_rebalance: bool = False

    _tick_spacing: int = 0
    _token_id: int = -1  # current token id
    _last_number_processed: int = 0
    _block_rebalance_last: int = 0  # last block rebalanced

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
            state (Mapping): The ref state at given block iteration.
        """
        mock_pool = self._mocks["pool"]
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
        mock_pool.calls(datas, sender=self.acc)

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
