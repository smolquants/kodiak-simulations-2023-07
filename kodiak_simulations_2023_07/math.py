import numpy as np

from scipy import pi
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
    Expected value of principal for LP at end of rebalance period per unit of amount1.
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
    Expected value of accumulated fees for LP at end of rebalance period per unit of amount1.
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
