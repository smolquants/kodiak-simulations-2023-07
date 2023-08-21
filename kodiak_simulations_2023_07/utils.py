# uni v3 utility functions
def get_sqrt_ratio_at_tick(tick: int) -> int:
    return int(((1.0001 ** (tick)) ** (1/2)) * (1 << 96))


def get_amount0_for_liquidity(
    sqrt_ratio_a_x96: int,
    sqrt_ratio_b_x96: int,
    liquidity: int
) -> int:
    return (
        ((liquidity * (1 << 96)) * (sqrt_ratio_b_x96 - sqrt_ratio_a_x96)) // sqrt_ratio_b_x96
    ) // sqrt_ratio_a_x96


def get_amount1_for_liquidity(
    sqrt_ratio_a_x96: int,
    sqrt_ratio_b_x96: int,
    liquidity: int
) -> int:
    return (liquidity * (sqrt_ratio_b_x96 - sqrt_ratio_a_x96)) // (1 << 96)


def get_amounts_for_liquidity(
    sqrt_ratio_x96: int,
    sqrt_ratio_a_x96: int,
    sqrt_ratio_b_x96: int,
    liquidity: int
) -> (int, int):
    # @dev only implemented for tick_lower <= state.tick <= tick_upper
    assert (sqrt_ratio_a_x96 <= sqrt_ratio_x96 and sqrt_ratio_x96 <= sqrt_ratio_b_x96)
    amount0 = get_amount0_for_liquidity(sqrt_ratio_x96, sqrt_ratio_b_x96, liquidity)
    amount1 = get_amount1_for_liquidity(sqrt_ratio_a_x96, sqrt_ratio_x96, liquidity)
    return (amount0, amount1)
