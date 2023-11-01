from typing import ClassVar

from .base import UniswapV3LPFixedWidthRunner


# fixed tick width lp runner class for simple backtesting
class UniswapV3LPSimpleRunner(UniswapV3LPFixedWidthRunner):
    _backtester_name: ClassVar[str] = "UniswapV3LPSimpleBacktest"
