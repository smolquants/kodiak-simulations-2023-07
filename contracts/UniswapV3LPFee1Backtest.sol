// SPDX-License-Identifier: MIT
pragma solidity 0.8.12;

import {Backtest} from "@smolquants/backtest-ape/contracts/Backtest.sol";
import {PositionValue} from "@uniswap/v3-periphery/contracts/libraries/PositionValue.sol";
import {INonfungiblePositionManager} from "@uniswap/v3-periphery/contracts/interfaces/INonfungiblePositionManager.sol";

/// @title Uniswap V3 Liquidity Provider Fee1 Backtester
/// @notice Backtests fee1 accumulation of an LP position in pool
contract UniswapV3LPFee1Backtest is Backtest {
    INonfungiblePositionManager public immutable manager;    
    uint256 public tokenId;
    
    constructor(address _manager) {
        manager = INonfungiblePositionManager(_manager);
    }
    
    /// @notice Pushes token id to storage to track NFT position
    function push(uint256 _tokenId) external {
        require(tokenId == 0, "tokenId already pushed");
        tokenId = _tokenId;
    }
    
    /// @notice Reports the amount0Fee of the LP token
    /// @return value_ The current token1 fees accumulated by LP token owned by this contract
    function value() public view virtual override returns (uint256 value_) {
        (uint256 amount0Fee, uint256 amount1Fee) = PositionValue.fees(manager, tokenId);
        value_ = amount1Fee;
    }
}
