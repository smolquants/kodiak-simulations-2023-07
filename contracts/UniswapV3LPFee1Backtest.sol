// SPDX-License-Identifier: MIT
pragma solidity 0.8.12;

import {UniswapV3LPBacktest} from "@smolquants/backtest-ape/contracts/uniswap/v3/UniswapV3LPBacktest.sol";
import {PositionValue} from "@uniswap/v3-periphery/contracts/libraries/PositionValue.sol";
import {INonfungiblePositionManager} from "@uniswap/v3-periphery/contracts/interfaces/INonfungiblePositionManager.sol";

/// @title Uniswap V3 Liquidity Provider Fee1 Backtester
/// @notice Backtests fee1 accumulation of an LP position in pool
contract UniswapV3LPFee1Backtest is UniswapV3LPBacktest {
    constructor(address _manager) UniswapV3LPBacktest(_manager) {}

    /// @notice Reports the amount1Fee of the LP token
    /// @return value_ The current token1 fees accumulated by LP token owned by this contract
    function value() public view virtual override returns (uint256 value_) {
        for (uint256 i = 0; i < tokenIds.length; ++i) {
            uint256 tokenId = tokenIds[i];
            (uint256 amount0Fee, uint256 amount1Fee) = PositionValue.fees(manager, tokenId);
            value_ += amount1Fee;
        }
    }
}
