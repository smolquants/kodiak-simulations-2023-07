// SPDX-License-Identifier: MIT
pragma solidity 0.8.12;

import {UniswapV3LPBacktest} from "@smolquants/backtest-ape/contracts/uniswap/v3/UniswapV3LPBacktest.sol";

import {IUniswapV3Pool} from "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
import {FixedPoint128} from "@uniswap/v3-core/contracts/libraries/FixedPoint128.sol";
import {FullMath} from "@uniswap/v3-core/contracts/libraries/FullMath.sol";
import {TickMath} from "@uniswap/v3-core/contracts/libraries/TickMath.sol";
import {LiquidityAmounts} from "@uniswap/v3-periphery/contracts/libraries/LiquidityAmounts.sol";

import {MockPositionValue as PositionValue} from "./uniswap/v3/mocks/libraries/MockPositionValue.sol";

/// @title Uniswap V3 Liquidity Provider Simple Backtester
/// @dev Redefined here for access in ape.project
/// @notice Backtests as simple pass through view on pool state: slot0.sqrtPriceX96, liquidity, feeGrowthGlobalX128
contract UniswapV3LPSimpleBacktest is UniswapV3LPBacktest {
    address public immutable pool_;

    // tick lower, upper for lp during period
    int24 public tickLower_;
    int24 public tickUpper_;

    // liquidity attributed to lp during period
    uint128 public liquidity_;

    // fee growth inside at start of lp period
    uint256 public feeGrowthInside0X128_;
    uint256 public feeGrowthInside1X128_;

    constructor(address _manager, address _token0, address _token1, uint24 _fee) UniswapV3LPBacktest(_manager) {
        pool_ = getPool(_token0, _token1, _fee);
    }

    function update(int24 _tickLower, int24 _tickUpper, uint128 _liquidity) external {
        tickLower_ = _tickLower;
        tickUpper_ = _tickUpper;
        liquidity_ = _liquidity;
        (feeGrowthInside0X128_, feeGrowthInside1X128_) = _getFeeGrowthInsideX128(pool_, _tickLower, _tickUpper);
    }

    /// @notice Reports the current pool state values needed to calculate historical LP values
    /// @return values_ The current pool feeGrowthGlobalX128 and feeGrowthInsideX128 values
    function values() public view virtual override returns (uint256[] memory values_) {
        values_ = new uint256[](4);

        (uint256 principal0, uint256 principal1) = principal(getSqrtRatioX96(pool_));
        values_[0] = principal0;
        values_[1] = principal1;

        (uint256 fees0, uint256 fees1) = fees();
        values_[2] = fees0;
        values_[3] = fees1;
    }

    /// @dev adatped from PositionValue.sol::principal
    function principal(uint160 sqrtRatioX96) public view returns (uint256 amount0, uint256 amount1) {
        return
            LiquidityAmounts.getAmountsForLiquidity(
                sqrtRatioX96,
                TickMath.getSqrtRatioAtTick(tickLower_),
                TickMath.getSqrtRatioAtTick(tickUpper_),
                liquidity_
            );
    }

    /// @dev adapted from PositionValue.sol::fees
    function fees() public view returns (uint256 amount0, uint256 amount1) {
        (uint256 poolFeeGrowthInside0LastX128, uint256 poolFeeGrowthInside1LastX128) = _getFeeGrowthInsideX128(
            pool_,
            tickLower_,
            tickUpper_
        );

        amount0 = FullMath.mulDiv(poolFeeGrowthInside0LastX128 - feeGrowthInside0X128_, liquidity_, FixedPoint128.Q128);
        amount1 = FullMath.mulDiv(poolFeeGrowthInside1LastX128 - feeGrowthInside1X128_, liquidity_, FixedPoint128.Q128);
    }

    function _getFeeGrowthGlobalX128(
        address pool
    ) private view returns (uint256 feeGrowthGlobal0X128, uint256 feeGrowthGlobal1X128) {
        feeGrowthGlobal0X128 = IUniswapV3Pool(pool_).feeGrowthGlobal0X128();
        feeGrowthGlobal1X128 = IUniswapV3Pool(pool_).feeGrowthGlobal1X128();
    }

    function _getFeeGrowthInsideX128(
        address pool,
        int24 tickLower,
        int24 tickUpper
    ) private view returns (uint256, uint256) {
        return PositionValue._getFeeGrowthInside(IUniswapV3Pool(pool_), tickLower_, tickUpper_);
    }
}
