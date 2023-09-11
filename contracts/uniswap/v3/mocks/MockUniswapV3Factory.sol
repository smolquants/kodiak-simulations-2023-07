// SPDX-License-Identifier: BUSL-1.1
pragma solidity 0.8.12;

import {MockUniswapV3PoolDeployer} from "./MockUniswapV3PoolDeployer.sol";

/// @dev DO NOT ACTUALLY DEPLOY
/// @dev See https://github.com/Uniswap/v3-core/blob/0.8/contracts/UniswapV3Factory.sol
contract MockUniswapV3Factory is MockUniswapV3PoolDeployer {
    mapping(address => mapping(address => mapping(uint24 => address))) public getPool;

    /// @notice Overrides to deploy the mock pool
    function createPool(address tokenA, address tokenB, uint24 fee) external returns (address pool) {
        (address token0, address token1) = tokenA < tokenB ? (tokenA, tokenB) : (tokenB, tokenA);
        int24 tickSpacing = fee == uint24(500)
            ? int24(10)
            : (fee == uint24(3000) ? int24(60) : (fee == uint24(10000) ? int24(200) : int24(0)));
        pool = deploy(address(this), token0, token1, fee, tickSpacing);
        getPool[token0][token1][fee] = pool;
    }
}
