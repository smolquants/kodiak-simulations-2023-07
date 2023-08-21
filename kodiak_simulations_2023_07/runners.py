from typing import ClassVar

from .base import UniswapV3LPFixedWidthBaseRunner


class UniswapV3LPFixedWidthFee0Runner(UniswapV3LPFixedWidthBaseRunner):
    _backtester_name: ClassVar[str] = "UniswapV3LPFee0Backtest"  # contract to check fee0 accumulation


class UniswapV3LPFixedWidthFee1Runner(UniswapV3LPFixedWidthBaseRunner):
    _backtester_name: ClassVar[str] = "UniswapV3LPFee0Backtest"  # contract to check fee1 accumulation
