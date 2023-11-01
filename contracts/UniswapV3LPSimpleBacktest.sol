// SPDX-License-Identifier: MIT
pragma solidity 0.8.12;

import {UniswapV3LPBacktest} from "@smolquants/backtest-ape/contracts/uniswap/v3/UniswapV3LPBacktest.sol";
import {IUniswapV3Pool} from "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
import {MockPositionValue as PositionValue} from "./uniswap/v3/mocks/libraries/MockPositionValue.sol";

/// @title Uniswap V3 Liquidity Provider Simple Backtester
/// @dev Redefined here for access in ape.project
/// @notice Backtests as simple pass through view on pool state: slot0.sqrtPriceX96, liquidity, feeGrowthGlobalX128
contract UniswapV3LPSimpleBacktest is UniswapV3LPBacktest {
    address public immutable pool_;

    // tick lower, upper for lp during period
    int24 public tickLower_;
    int24 public tickUpper_;

    // fee growth inside at start of lp period
    uint256 public feeGrowthInside0X128_;
    uint256 public feeGrowthInside1X128_;

    constructor(address _manager, address _token0, address _token1, uint24 _fee) UniswapV3LPBacktest(_manager) {
        pool_ = getPool(_token0, _token1, _fee);
    }

    function update(int24 _tickLower, int24 _tickUpper) external {
        tickLower_ = _tickLower;
        tickUpper_ = _tickUpper;

        (feeGrowthInside0X128_, feeGrowthInside1X128_) = getFeeGrowthInsideX128(pool_, _tickLower, _tickUpper);
    }

    /// @notice Reports the current pool state values needed to calculate historical LP values
    /// @return values_ The current pool sqrtPriceX96, liquidity, feeGrowthGlobalX128 values
    function values() public view virtual override returns (uint256[] memory values_) {
        values_ = new uint256[](6);
        values_[0] = uint256(getSqrtRatioX96(pool_));
        values_[1] = uint256(getLiquidity(pool_));

        (uint256 feeGrowthGlobal0X128, uint256 feeGrowthGlobal1X128) = getFeeGrowthGlobalX128(pool_);
        values_[2] = feeGrowthGlobal0X128;
        values_[3] = feeGrowthGlobal1X128;

        (uint256 feeGrowthInside0X128, uint256 feeGrowthInside1X128) = getFeeGrowthInsideX128(
            pool_,
            tickLower_,
            tickUpper_
        );
        values_[4] = feeGrowthInside0X128;
        values_[5] = feeGrowthInside1X128;
    }

    function getLiquidity(address pool) public view returns (uint128) {
        return IUniswapV3Pool(pool_).liquidity();
    }

    function getFeeGrowthGlobalX128(
        address pool
    ) public view returns (uint256 feeGrowthGlobal0X128, uint256 feeGrowthGlobal1X128) {
        feeGrowthGlobal0X128 = IUniswapV3Pool(pool_).feeGrowthGlobal0X128();
        feeGrowthGlobal1X128 = IUniswapV3Pool(pool_).feeGrowthGlobal1X128();
    }

    function getFeeGrowthInsideX128(
        address pool,
        int24 tickLower,
        int24 tickUpper
    ) public view returns (uint256, uint256) {
        return PositionValue.getFeeGrowthInside(IUniswapV3Pool(pool_), tickLower_, tickUpper_);
    }
}
