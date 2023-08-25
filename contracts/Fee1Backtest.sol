// SPDX-License-Identifier: MIT
pragma solidity 0.8.12;

import {UniswapV3LPFee1Backtest} from "@smolquants/backtest-ape/contracts/uniswap/v3/UniswapV3LPFee1Backtest.sol";

/// @title Uniswap V3 Liquidity Provider Fee1 Backtester
/// @dev Redefined here for access in ape.project
/// @notice Backtests fee1 accumulation of an LP position in pool
contract Fee1Backtest is UniswapV3LPFee1Backtest {
    constructor(address _manager) UniswapV3LPFee1Backtest(_manager) {}
}
