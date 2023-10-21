import click
import numpy as np

from ape import Contract, chain, networks
from scipy import integrate, optimize
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

    def _integrand(_t: float) -> float:
        _m = m(mu, tau)  # should be tau here since selling fees at end of rebalance period
        _dp = dp(delta, mu, sigma, _t)
        _dm = dm(delta, mu, sigma, _t)
        _s = s(sigma, _t)
        return norm.cdf(_dp) - norm.cdf(_dm) + np.exp(_m) * (np.exp(_dp - _s) - np.exp(_dm - _s))

    _factor = theta / (1 - np.exp(-delta / 2) + el)
    return _factor * integrate.quad(_integrand, 0, tau)[0]  # TODO: check error at index 1


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
    last_block_number = chain.blocks.head.number

    # ask user for uni v3 pool data for price history, volume, current liquidity conditions
    # @dev must conform to univ3 core abi
    pool_addr = click.prompt("Pool address", type=str)
    pool = Contract(pool_addr)

    # get the existing liquidity conditions
    liquidity = pool.liquidity(block_identifier=last_block_number)
    sqrt_price_x96 = pool.slot0(block_identifier=last_block_number).sqrtPriceX96
    ef = pool.fee() / 1e6

    # get avg fee revenues over last rebalance period
    tau = click.prompt("Rebalance period in blocks (tau)", type=int)

    fee_growth0_x128_start = pool.feeGrowthGlobal0X128(block_identifier=last_block_number - tau)
    fee_growth0_x128_end = pool.feeGrowthGlobal0X128(block_identifier=last_block_number)
    theta0 = ((fee_growth0_x128_end - fee_growth0_x128_start) * sqrt_price_x96) / (tau * (1 << 224))

    fee_growth1_x128_start = pool.feeGrowthGlobal0X128(block_identifier=last_block_number - tau)
    fee_growth1_x128_end = pool.feeGrowthGlobal0X128(block_identifier=last_block_number)
    theta1 = (fee_growth1_x128_end - fee_growth1_x128_start) / (tau * sqrt_price_x96 * (1 << 32))

    theta = (theta0 + theta1) / 2
    click.echo(f"Avg fees per unit of virtual liquidity over last rebalance period (theta): {theta}")

    # ask user for amount of liquidity to deploy
    amount1 = click.prompt("Amount of token1 to LP", type=int)
    el = (amount1 * (1 << 96)) / (liquidity * sqrt_price_x96)
    click.echo(f"Liquidity to deploy per unit of virtual liquidity (l): {el}")

    # ask user for per block drift, vol of pool price
    # @dev use fit.py script to determine
    mu = click.prompt("Log-price per block drift (mu)", type=int)
    sigma = click.prompt("Log-price per block volatility (sigma)", type=int)

    theta_min = (sigma**2) * (el + 1) / 8
    click.echo(f"Minimum theta for +EV: {theta_min}")
    if theta < theta_min:
        click.echo("WARNING: Not enough fees over last rebalance period for +EV LPing")
        if not click.confirm("Proceed anyway?"):
            return

    # define EV function to optimize wrt tick width
    def ev(delta: float) -> float:
        return rho(delta, mu, sigma, tau, ef, el) + psi(delta, mu, sigma, tau, theta, el)

    # use sigma * sqrt(tau) as initial guess
    click.echo("Optimizing EV with respect to tick width ...")
    x0 = s(sigma, tau)
    res = optimize.minimize(-ev, x0)

    click.echo(f"Result from scipy.optimize.minimize: {res}")
    click.echo(f"Tick width delta={res.x} maximizes LP expected value at EV={res.fun}.")
