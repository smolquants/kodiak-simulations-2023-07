// SPDX-License-Identifier: MIT
pragma solidity 0.8.12;

import {UniswapV3LPBacktest} from "@smolquants/backtest-ape/contracts/uniswap/v3/UniswapV3LPBacktest.sol";
import {MockPositionValue as PositionValue} from "./uniswap/v3/mocks/libraries/MockPositionValue.sol";

/// @title Uniswap V3 Liquidity Provider Full Backtester
/// @dev Redefined here for access in ape.project
/// @notice Backtests principal, fee accumulation of an LP position in pool in both (token0, token1)
contract UniswapV3LPFullBacktest is UniswapV3LPBacktest {
    constructor(address _manager) UniswapV3LPBacktest(_manager) {}
    
    /// @notice Reports the principal, fee (token0, token1) values of the LP tokens owned by this contract
    /// @return values_ The current (token0, token1) principal, fee of the LP tokens owned by this contract
    function values() public view virtual override returns (uint256[] memory values_) {
        values_ = new uint256[](4);
        for (uint256 i = 0; i < tokenIds.length; ++i) {
            uint256 tokenId = tokenIds[i];
            (, , address token0, address token1, uint24 fee, , , , , , , ) = manager.positions(tokenId);

            // get the sqrt price
            address pool = getPool(token0, token1, fee);
            uint160 sqrtRatioX96 = getSqrtRatioX96(pool);

            // get the amounts for each category
            (uint256 amount0Principal, uint256 amount1Principal) = PositionValue.principal(
                address(manager),
                tokenId,
                sqrtRatioX96
            );
            (uint256 amount0Fee, uint256 amount1Fee) = PositionValue.fees(address(manager), tokenId);

            // set values in return array
            values_[0] += amount0Principal;
            values_[1] += amount1Principal;
            values_[2] += amount0Fee;
            values_[3] += amount1Fee;
        }
    }
}
