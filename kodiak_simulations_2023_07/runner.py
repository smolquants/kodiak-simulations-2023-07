import os
import pandas as pd

from ape import chain
from backtest_ape.uniswap.v3 import UniswapV3LPBaseRunner
from backtest_ape.uniswap.v3.lp.mgmt import mint_lp_position, remove_liquidity_from_lp_position
from typing import Any, ClassVar, List, Mapping

from .utils import get_sqrt_ratio_at_tick, get_amounts_for_liquidity


# fixed tick width lp runner classes for backtesting
class UniswapV3LPFixedWidthRunner(UniswapV3LPBaseRunner):
    liquidity: int = 0  # liquidity contribution by LP
    tick_width: int = 0  # 2 * delta
    blocks_between_rebalance: int = 0  # blocks between rebalances (assumes fixed blocktimes)

    _token_id: int = 1  # current token id
    _block_rebalance_last: int = 0  # last block rebalanced
    _backtester_name: ClassVar[str] = "UniswapV3LPFullBacktest"
    _tick_spacing: int

    def __init__(self, **data: Any):
        """
        Overrides UniswapV3LPRunner to check tick width // 2 is a multiple of pool
        tick spacing.
        """
        super().__init__(**data)

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
        (
            _,
            _,
            _,
            _,
            _,
            _,
            _,
            liquidity,
            _,
            _,
            _,
            _
        ) = manager.positions(token_id)
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
        tick = state["slot0"].tick - remainder \
            if remainder < self._tick_spacing // 2 \
            else state["slot0"].tick + (self._tick_spacing - remainder)

        # fixed width straddles closest tick to current state
        tick_lower = tick - self.tick_width // 2
        tick_upper = tick + self.tick_width // 2
        return (tick_lower, tick_upper)

    def init_mocks_state(self, state: Mapping):
        """
        Overrides UniswapV3LPRunner to use tick width and store liquidity contribution by LP.

        Args:
            state (Mapping): The init state of mocks.
        """
        # TODO: check whether issue minting on manager with fee accounting after set mock state
        # some setup based off initial state
        tick_lower, tick_upper = self._calculate_lp_ticks(state)
        self.tick_lower = tick_lower
        self.tick_upper = tick_upper

        (amount0_desired, amount1_desired) = get_amounts_for_liquidity(
            get_sqrt_ratio_at_tick(state["slot0"].tick),  # sqrt_ratio_x96
            get_sqrt_ratio_at_tick(self.tick_lower),  # sqrt_ratio_a_x96
            get_sqrt_ratio_at_tick(self.tick_upper),  # sqrt_ratio_b_x96
            self.liquidity,
        )
        self.amount0 = amount0_desired
        self.amount1 = amount1_desired

        super().init_mocks_state(state)

        # store the actual liquidity minted
        self.liquidity = self._get_position_liquidity(self._token_id)

    def update_strategy(self, number: int, state: Mapping):
        """
        Updates the strategy being backtested through backtester contract.

        Rebalances symmetrically around current tick, with
          - tick_lower = tick_current - tick_width // 2
          - tick_upper = tick_current + tick_width // 2
        """
        if self._block_rebalance_last == 0:
            self._block_rebalance_last = number
            return
        elif number < self._block_rebalance_last + self.blocks_between_rebalance:
            return

        self._block_rebalance_last = number

        # some needed local vars
        mock_pool = self._mocks["pool"]
        mock_tokens = self._mocks["tokens"]
        mock_manager = self._mocks["manager"]
        ecosystem = chain.provider.network.ecosystem

        # pull principal from existing position
        remove_liquidity_from_lp_position(
            mock_manager,
            mock_pool,
            self.backtester,
            self._token_id,
            self.liquidity,
            self.acc,
        )

        # mint a new position after "rebalancing" liquidity
        tick_lower, tick_upper = self._calculate_lp_ticks(state)
        self.tick_lower = tick_lower
        self.tick_upper = tick_upper

        (amount0_desired, amount1_desired) = get_amounts_for_liquidity(
            get_sqrt_ratio_at_tick(state["slot0"].tick),  # sqrt_ratio_x96
            get_sqrt_ratio_at_tick(self.tick_lower),  # sqrt_ratio_a_x96
            get_sqrt_ratio_at_tick(self.tick_upper),  # sqrt_ratio_b_x96
            self.liquidity,
        )

        # mint or burn tokens from backtester to "rebalance"
        # @dev assumes infinite external liquidity for pair (and zero fees)
        del_amount0 = amount0_desired - mock_tokens[0].balanceOf(self.backtester.address)
        del_amount1 = amount1_desired - mock_tokens[1].balanceOf(self.backtester.address)

        targets = [mock_tokens[0].address, mock_tokens[1].address]
        datas = [
            ecosystem.encode_transaction(
                mock_tokens[0].address,
                mock_tokens[0].mint.abis[0],
                self.backtester.address,
                del_amount0,
            ).data if del_amount0 > 0 else ecosystem.encode_transaction(
                mock_tokens[0].address,
                mock_tokens[0].burn.abis[0],
                self.backtester.address,
                -del_amount0,
            ).data,
            ecosystem.encode_transaction(
                mock_tokens[1].address,
                mock_tokens[1].mint.abis[0],
                self.backtester.address,
                del_amount1,
            ).data if del_amount1 > 0 else ecosystem.encode_transaction(
                mock_tokens[1].address,
                mock_tokens[1].burn.abis[0],
                self.backtester.address,
                -del_amount1
            ).data
        ]
        values = [0, 0]
        self.backtester.multicall(targets, datas, values, sender=self.acc)

        self.amount0 = amount0_desired
        self.amount1 = amount1_desired

        # mint the lp position
        mint_lp_position(
            mock_manager,
            mock_pool,
            self.backtester,
            [self.tick_lower, self.tick_upper],
            [self.amount0, self.amount1],
            self.acc,
        )
        self._token_id = self.backtester.count() + 1
        self.liquidity = self._get_position_liquidity(self._token_id)

        # store token id in backtester
        self.backtester.push(self._token_id, sender=self.acc)

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

        data.update({
            "sqrtPriceX96": state["slot0"].sqrtPriceX96,
            "tick": state["slot0"].tick,
            "liquidity": state["liquidity"],
            "position_token_id": self._token_id,
            "position_liquidity": self.liquidity,
            "position_tick_lower": self.tick_lower,
            "position_tick_upper": self.tick_upper,
        })

        header = not os.path.exists(path)
        df = pd.DataFrame(data={k: [v] for k, v in data.items()})
        df.to_csv(path, index=False, mode="a", header=header)
