import click
import numpy as np
import pandas as pd

from ape import Contract, chain, networks
from kodiak_simulations_2023_07.optimize import find_optimal_delta


def main():
    """
    Main optimize script for determining optimal tick width given:
      - Uni v3 pool data
      - Rebalance period (tau)
      - Liquidity to deploy in pool (l)

    Assumes GBM for underlying price process.
    """
    # echo provider setup
    ecosystem_name = networks.provider.network.ecosystem.name
    network_name = networks.provider.network.name
    provider_name = networks.provider.name
    connection_name = f"{ecosystem_name}:{network_name}:{provider_name}"
    click.echo(f"You are connected to provider network {connection_name}.")

    # fail if not mainnet-fork
    if network_name != "mainnet-fork":
        raise ValueError("not connected to mainnet-fork.")

    # get last block
    block_number = click.prompt("Start block for LP", type=int, default=-1)
    if block_number < 0:
        block_number = chain.blocks.head.number  # last block number is default

    # ask user for uni v3 pool data for price history, volume, current liquidity conditions
    # @dev must conform to univ3 core abi
    pool_addr = click.prompt("Pool address", type=str)
    pool = Contract(pool_addr)

    # get the existing liquidity conditions
    liquidity = pool.liquidity(block_identifier=block_number)
    slot0 = pool.slot0(block_identifier=block_number)
    sqrt_price_x96 = slot0.sqrtPriceX96
    ef = pool.fee() / 1e6
    tick_spacing = pool.tickSpacing()
    delta_min = np.log(1.0001 ** (tick_spacing // 2))
    click.echo(f"Pool liquidity (L): {liquidity}")
    click.echo(f"Pool sqrt price (sqrtPriceX96): {sqrt_price_x96}")
    click.echo(f"Pool fee (f): {ef}")
    click.echo(f"Pool tick spacing in natural log terms (delta_min): {delta_min}")

    # get avg fee revenues over last rebalance period
    tau = click.prompt("Rebalance period in blocks (tau)", type=int)

    fee_growth0_x128_start = pool.feeGrowthGlobal0X128(block_identifier=block_number - tau)
    fee_growth0_x128_end = pool.feeGrowthGlobal0X128(block_identifier=block_number)
    theta0 = ((fee_growth0_x128_end - fee_growth0_x128_start) * sqrt_price_x96) / (tau * (1 << 224))
    click.echo(f"Avg fees from fee growth with token0 in (theta0): {theta0}")

    fee_growth1_x128_start = pool.feeGrowthGlobal1X128(block_identifier=block_number - tau)
    fee_growth1_x128_end = pool.feeGrowthGlobal1X128(block_identifier=block_number)
    theta1 = (fee_growth1_x128_end - fee_growth1_x128_start) / (tau * sqrt_price_x96 * (1 << 32))
    click.echo(f"Avg fees from fee growth with token1 in (theta1): {theta1}")

    theta = (theta0 + theta1) / 2
    click.echo(f"Avg fees per unit of virtual liquidity over last rebalance period (theta): {theta}")

    # ask user for amount of liquidity to deploy
    amount1 = click.prompt("Amount of token1 to LP", type=int)
    el = (amount1 * (1 << 96)) / (liquidity * sqrt_price_x96)
    click.echo(f"Liquidity to deploy per unit of virtual liquidity (l): {el}")

    # ask user for per block drift, vol of pool price
    # @dev use fit.py script to determine
    mu = click.prompt("Log-price per block drift (mu)", type=float)
    sigma = click.prompt("Log-price per block volatility (sigma)", type=float)

    theta_min = (el + 1) * sigma**2 / 8
    click.echo(f"Minimum theta for +EV at infinite tick width (approx): {theta_min}")
    if theta < theta_min:
        click.echo(
            "WARNING: Not enough fees over last rebalance period for +EV LPing at infinite tick width when ignoring drift (approx)."
        )
        if not click.confirm("Proceed anyway?"):
            return

    click.echo("Optimizing EV with respect to tick width ...")
    (delta, value) = find_optimal_delta(mu, sigma, tau, ef, el, theta, tick_spacing)

    y = value - 1
    click.echo(f"Optimal tick width (delta): {delta}")
    click.echo(f"Expected value at optimal tick width (E[V(tau)/V(0)]): {value}")
    click.echo(f"Expected yield at optimal tick width (E[V(tau)/V(0)-1]): {y}")

    remainder = slot0.tick % tick_spacing
    tick = slot0.tick - remainder if remainder < tick_spacing // 2 else slot0.tick + (tick_spacing - remainder)

    tick_width = int((2 * delta) / np.log(1.0001))
    tick_width = tick_spacing * (tick_width // tick_spacing)  # make sure multiple of tick spacing

    tick_lower = tick - tick_width // 2
    tick_upper = tick + tick_width // 2
    click.echo(f"Current tick: {slot0.tick}")
    click.echo(f"Suggested lower tick for next period: {tick_lower}")
    click.echo(f"Suggested upper tick for next period: {tick_upper}")

    # save to csv
    path = f"notebook/results/optimize/delta_{pool_addr}_{block_number}_{tau}_{amount1}.csv"
    data = {
        "delta": [delta],
        "value": [value],
        "yield": [y],
        "tick_width": [tick_width],
        "tick": [slot0.tick],
        "tick_lower": [tick_lower],
        "tick_upper": [tick_upper],
        "el": [el],
        "theta": [theta],
        "tau": [tau],
        "mu": [mu],
        "sigma": [sigma],
    }
    df = pd.DataFrame(data=data)
    df.to_csv(path, index=False)
