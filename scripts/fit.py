import click
import numpy as np
import pandas as pd

from scipy.stats import norm


def main():
    """
    Main fit script determines log-price parameters for a given pool.

    Assumes GBM for underlying price process.
    """
    # ask user for price history csv
    # @dev use query.py script to gather
    fp = click.prompt("Path to price history csv", type=str)
    df = pd.read_csv(fp)

    # df must contain sqrt_price_x96 col
    if not set(['block_number', 'sqrt_price_x96']).issubset(set(list(df.columns))):
        _cols = set(['block_number', 'sqrt_price_x96'])
        _missing_cols = _cols.difference(_cols.intersection(set(list(df.columns))))
        click.echo(f"Given csv file does not have required columns {list(_missing_cols)}. Exiting script ...")
        return

    def price(sqrt_price_x96: int) -> int:
        return (int(sqrt_price_x96) ** 2) // (1 << 192)

    df['price'] = df['sqrt_price_x96'].apply(price)
    df['dlog(p)'] = np.log(df['price']).diff()

    # fit to log normal
    # @dev ignore null first row from diff()
    click.echo("Fitting log-price history to GBM ...")
    data = df[df['dlog(p)'].notnull()]['dlog(p)']
    params = norm.fit(data)
    click.echo("Returned fit params:", params)

    t = df['block_number'].diff()[1]  # @dev assumes candles are uniform
    mu_p = params[-2] / t
    sigma = params[-1] / np.sqrt(t)
    mu = mu_p + sigma**2 / 2

    click.echo("Drift per block (mu):", mu)
    click.echo("Volatility per block (sigma):", sigma)
