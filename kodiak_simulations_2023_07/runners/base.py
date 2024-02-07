import click
import os
import pandas as pd

from typing import Any, List, Mapping

from backtest_ape.uniswap.v3 import UniswapV3LPBaseRunner
from backtest_ape.setup import deploy_mock_erc20
from backtest_ape.uniswap.v3.setup import (
    deploy_mock_position_manager,
    deploy_mock_univ3_factory,
)

from ..constants import MAX_TICK
from .setup import create_mock_pool


# fixed tick width lp runner classes for backtesting
class UniswapV3LPFixedWidthRunner(UniswapV3LPBaseRunner):
    liquidity: int = 0  # liquidity contribution by LP
    tick_width: int = 0  # 2 * delta
    blocks_between_rebalance: int = 0  # tau
    compound_fees_at_rebalance: bool = False

    _tick_spacing: int = 0  # tick width around initial tick
    _token_id: int = -1  # current token id
    _last_number_processed: int = 0
    _block_rebalance_last: int = 0  # last block rebalanced

    _fees0_cumulative: int = 0  # tracks cumulative fees in token0
    _fees1_cumulative: int = 0  # tracks cumulatives fees in token1

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

    def _calculate_lp_ticks(self, number: int, state: Mapping) -> (int, int):
        """
        Calculates anticipated tick upper and lower with fixed width around
        current tick.

        Args:
            number (int): The block number used for mock state reference.
            state (Mapping): The state of mocks.
        """
        # if tick width == 0, then full range LPing
        if self.tick_width == 0:
            tick_upper = MAX_TICK - (MAX_TICK % self._tick_spacing)
            tick_lower = -tick_upper
            return (tick_lower, tick_upper)

        # otherwise rebalance around current tick
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

        # check for next ticks if uninitialized
        # @dev will widen tick width
        (tick_lower, tick_upper) = self._find_nearest_lp_ticks(number, tick, tick_lower, tick_upper)
        return (tick_lower, tick_upper)

    def _find_nearest_lp_ticks(self, number: int, tick: int, tick_lower: int, tick_upper: int) -> (int, int):
        """
        Finds nearest ticks to tick upper and lower in case given ticks are uninitialized.
        Widens the actual tick width LP uses if either tick is uninitialized in reference.

        Args:
            tick (int): Tick to LP around
            tick_lower (int): Initial guess for tick lower to LP with
            tick_upper (int): Initial guess for tick upper to LP with
        """
        click.echo(f"Finding nearest initialized ticks to ({tick_lower}, {tick_upper}) at block {number} ...")
        tick_width = tick_upper - tick_lower
        pool = self._refs["pool"]

        found = False
        while not found:
            click.echo(f"Checking ({tick_lower}, {tick_upper}) at block {number} ...")
            (_, _, _, _, _, _, _, lower_initialized) = pool.ticks(tick_lower)
            (_, _, _, _, _, _, _, upper_initialized) = pool.ticks(tick_upper)

            click.echo(f"Lower initialized: {lower_initialized}")
            click.echo(f"Upper initialized: {upper_initialized}")

            found = lower_initialized and upper_initialized
            click.echo(f"Found: {found}")
            if not found:
                tick_width += 2 * self._tick_spacing
                tick_lower = tick - tick_width // 2
                tick_upper = tick + tick_width // 2

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
                "feeGrowthGlobal0X128": state["fee_growth_global0_x128"],
                "feeGrowthGlobal1X128": state["fee_growth_global1_x128"],
                "position_token_id": self._token_id,
                "position_liquidity": self.liquidity,
                "position_tick_lower": self.tick_lower,
                "position_tick_upper": self.tick_upper,
                "position_amount0": self.amount0,
                "position_amount1": self.amount1,
                "position_fees0_cumulative": self._fees0_cumulative,
                "position_fees1_cumulative": self._fees1_cumulative,
            }
        )

        header = not os.path.exists(path)
        df = pd.DataFrame(data={k: [v] for k, v in data.items()})
        df.to_csv(path, index=False, mode="a", header=header)

    def deploy_mocks(self):
        """
        Deploys the mock contracts.
        """
        # deploy the mock erc20s
        click.echo("Deploying mock ERC20 tokens ...")
        mock_tokens = [
            deploy_mock_erc20(f"Mock Token{i}", token.symbol(), token.decimals(), self.acc)
            for i, token in enumerate(self._refs["tokens"])
        ]

        # deploy weth if necessary
        mock_weth = mock_tokens[0] if mock_tokens[0].symbol() == "WETH" else mock_tokens[1]
        if mock_weth.symbol() != "WETH":
            mock_weth = deploy_mock_erc20("Mock WETH9", "WETH", 18, self.acc)

        # deploy the mock univ3 factory
        click.echo("Deploying mock Uniswap V3 factory ...")
        mock_factory = deploy_mock_univ3_factory(self.acc)

        # deploy the mock NFT position manager
        # NOTE: uses zero address for descriptor so tokenURI will fail
        click.echo("Deploying the mock position manager ...")
        mock_manager = deploy_mock_position_manager(mock_factory, mock_weth, self.acc)

        # create the pool through the mock univ3 factory
        pool = self._refs["pool"]
        fee = pool.fee()
        sqrt_price_x96 = pool.slot0().sqrtPriceX96
        mock_pool = create_mock_pool(
            mock_factory,
            mock_tokens,
            fee,
            sqrt_price_x96,
            self.acc,
        )

        self._mocks = {
            "tokens": mock_tokens,
            "factory": mock_factory,
            "manager": mock_manager,
            "pool": mock_pool,
        }
