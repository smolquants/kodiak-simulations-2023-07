import click
import numpy as np

from scipy import optimize
from .constants import MAX_TICK
from .math import rho, psi, s


def find_optimal_delta(
    mu: float,
    sigma: float,
    tau: float,
    ef: float,
    el: float,
    theta: float,
    tick_spacing: float,
) -> (float, float):
    """
    Finds optimal delta to LP with using EV function to optimized
    with respect to delta.

    Returns:
        delta (float): The optimal delta to LP with
        value (float): EV under GBM at the optimal delta, normalized to 1 when tau = 0
    """

    # @dev Return negative as looking for maximum via scipy.optimize.minimize
    def ev(delta: float) -> float:
        return -(rho(delta, mu, sigma, tau, ef, el) + psi(delta, mu, sigma, tau, theta, el))

    delta_min = np.log(1.0001 ** (tick_spacing // 2))
    delta_max = np.log(1.0001 ** (MAX_TICK - (MAX_TICK % tick_spacing)))  # full tick width given pool tick spacing

    # use sigma * sqrt(tau) as initial guess
    x0 = s(sigma, tau)
    res = optimize.minimize(ev, x0, bounds=[(delta_min, None)])

    click.echo("Result from scipy.optimize.minimize ...")
    click.echo(f"{res}")

    delta = res.x[0] if res.success else delta_max
    value = -ev(delta) / 2
    return (delta, value)
