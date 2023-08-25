// SPDX-License-Identifier: MIT
pragma solidity 0.8.12;

import {UniswapV3LPFee0Backtest} from "@smolquants/backtest-ape/contracts/uniswap/v3/UniswapV3LPFee0Backtest.sol";

/// @title Uniswap V3 Liquidity Provider Fee0 Backtester
/// @dev Redefined here for access in ape.project
/// @notice Backtests fee0 accumulation of an LP position in pool
contract Fee0Backtest is UniswapV3LPFee0Backtest {
    constructor(address _manager) UniswapV3LPFee0Backtest(_manager) {}
}
