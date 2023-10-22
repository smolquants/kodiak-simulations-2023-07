import click
import numpy as np

from ape import Contract, chain, networks
from scipy import optimize, pi
from scipy.special import erf
from scipy.stats import norm


def s(sigma: float, tau: float) -> float:
    return sigma * np.sqrt(tau)


def m(mu: float, tau: float) -> float:
    return mu * tau


def mp(mu: float, sigma: float, tau: float) -> float:
    return (mu - sigma**2 / 2) * tau


def dp(delta: int, mu: int, sigma: int, tau: float) -> float:
    """
    d_{+}
    """
    _mp = mp(mu, sigma, tau)
    _s = s(sigma, tau)
    return (delta - _mp) / _s


def dm(delta: float, mu: float, sigma: float, tau: float) -> float:
    """
    d_{-}
    """
    _mp = mp(mu, sigma, tau)
    _s = s(sigma, tau)
    return (-delta - _mp) / _s


def rho(delta: float, mu: float, sigma: float, tau: float, ef: float, el: float) -> float:
    """
    Expected value of principal at end of rebalance period per unit of amount1.
    """
    _dp = dp(delta, mu, sigma, tau)
    _dm = dm(delta, mu, sigma, tau)
    _mp = mp(mu, sigma, tau)
    _m = m(mu, tau)
    _s = s(sigma, tau)

    # Principal before rebalance
    _rho_1a = (1 + np.exp(delta / 2)) * (np.exp(_m) * norm.cdf(_dm - _s) + 1 - norm.cdf(_dp))
    _rho_1b = (2 * np.exp((_m - _s**2 / 4) / 2) / (1 - np.exp(-delta / 2))) * (
        norm.cdf(_dp - _s / 2) - norm.cdf(_dm - _s / 2)
    )
    _rho_1c = -(1 / (np.exp(delta / 2) - 1)) * (
        norm.cdf(_dp) - norm.cdf(_dm) + np.exp(_m) * (norm.cdf(_dp - _s) - norm.cdf(_dm - _s))
    )
    _rho_1 = _rho_1a + _rho_1b + _rho_1c

    # Swap fees on rebalance
    _rho_2a = -(ef / 2) * (1 + np.exp(delta / 2)) * (np.exp(_m) * norm.cdf(_dm - _s) + 1 - norm.cdf(_dp))
    _rho_2b = (
        -(ef / 2)
        * (1 / (np.exp(delta / 2) - 1))
        * (
            np.exp(_m) * norm.cdf(_dp - _s)
            + norm.cdf(_dm - _s)
            - 2 * norm.cdf(-_mp / _s - _s)
            + 2 * norm.cdf(-_mp / _s)
            - norm.cdf(_dp)
            - norm.cdf(_dm)
        )
    )
    _rho_2 = _rho_2a + _rho_2b

    # Slippage lost on rebalance
    _rho_3a = (
        -(el / 4)
        * ((np.exp(delta / 2) + 1) ** 2)
        * np.exp((_m + 3 * _s**2 / 4) / 2)
        * (np.exp(-_m) * (1 - norm.cdf(_dp + _s / 2)) + np.exp(_m) * norm.cdf(_dm - 3 * _s / 2))
    )
    _rho_3b = (
        -(el / 4)
        * (np.exp((_m + 3 * _s**2 / 4) / 2) / (np.exp(delta / 2) - 1) ** 2)
        * (
            np.exp(_m) * (norm.cdf(_dp - 3 * _s / 2) - norm.cdf(_dm - 3 * _s / 2))
            + np.exp(-_m) * (norm.cdf(_dp + _s / 2) - norm.cdf(_dm + _s / 2))
        )
    )
    _rho_3c = (
        (el / 2)
        * (np.exp((_m - _s**2 / 4) / 2) / (np.exp(delta / 2) - 1) ** 2)
        * (norm.cdf(_dp - _s / 2) - norm.cdf(_dm - _s / 2))
    )
    _rho_3 = _rho_3a + _rho_3b + _rho_3c

    return _rho_1 + _rho_2 + _rho_3


def psi(delta: float, mu: float, sigma: float, tau: float, theta: float, el: float) -> float:
    """
    Expected value of accumulated fees at end of rebalance period per unit of amount1.
    """
    # TODO: Fix so not rough approx as below (ignores O(_s**2))
    _m = m(mu, tau)
    _dap = delta / (sigma * np.sqrt(tau))
    _factor = theta / (1 - np.exp(-delta / 2) + el)
    _integ = (
        ((delta / sigma) ** 2 + tau) * erf(_dap / np.sqrt(2))
        + np.sqrt(2 / pi) * (delta / sigma) * np.sqrt(tau) * np.exp(-((_dap) ** 2) / 2)
        - (delta / sigma) ** 2
    )
    return _factor * _integ * (1 + np.exp(_m))


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

    # define EV function to optimize wrt tick width
    # @dev return negative as looking for maximum via scipy.optimize.minimize
    def ev(delta: float) -> float:
        return -(rho(delta, mu, sigma, tau, ef, el) + psi(delta, mu, sigma, tau, theta, el))

    # use sigma * sqrt(tau) as initial guess
    click.echo("Optimizing EV with respect to tick width ...")
    x0 = s(sigma, tau)
    res = optimize.minimize(ev, x0, bounds=[(delta_min, None)])

    y = -ev(res.x) / 2 - 1
    click.echo(f"Result from scipy.optimize.minimize: {res}")
    click.echo(f"Optimal tick width (delta): {res.x}")
    click.echo(f"Expected value at optimal tick width (E[V(tau)/V(0)]): {-ev(res.x)/2}")
    click.echo(f"Expected yield at optimal tick width (E[V(tau)/V(0)-1]): {y}")

    delta = res.x
    remainder = slot0.tick % tick_spacing
    tick = slot0.tick - remainder if remainder < tick_spacing // 2 else slot0.tick + (tick_spacing - remainder)

    tick_width = int((2 * delta) / np.log(1.0001))
    tick_lower = tick - tick_width // 2
    tick_upper = tick + tick_width // 2
    click.echo(f"Current tick: {slot0.tick}")
    click.echo(f"Suggested lower tick for next period: {tick_lower}")
    click.echo(f"Suggested upper tick for next period: {tick_upper}")
