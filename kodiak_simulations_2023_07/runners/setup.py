from typing import List

from ape import project
from ape.api.accounts import AccountAPI
from ape.contracts import ContractInstance
from ape.utils import ZERO_ADDRESS


def create_mock_pool(
    factory: ContractInstance,
    tokens: List[ContractInstance],
    fee: int,
    sqrt_price_x96: int,
    acc: AccountAPI,
) -> ContractInstance:
    """
    Creates mock Uniswap V3 pool through factory.

    Returns:
        :class:`ape.contracts.ContractInstance`
    """
    [tokenA, tokenB] = tokens
    factory.createPool(tokenA.address, tokenB.address, fee, sender=acc)
    pool_addr = factory.getPool(tokenA.address, tokenB.address, fee)
    if pool_addr == ZERO_ADDRESS:
        pool_addr = factory.getPool(tokenB.address, tokenA.address, fee)

    pool = project.MockUniswapV3Pool.at(pool_addr)

    # initialize the pool prior to returning
    pool.initialize(sqrt_price_x96, sender=acc)
    return pool
