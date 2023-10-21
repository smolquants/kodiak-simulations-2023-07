import click
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from scipy.stats import norm, probplot


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
    click.echo(f"Returned fit params for candles in csv: {params}")

    t = df['block_number'].diff()[1]  # @dev assumes candles are uniform
    mu_p = params[-2] / t
    sigma = params[-1] / np.sqrt(t)
    mu = mu_p + sigma**2 / 2

    click.echo(f"Log-price per block drift (mu): {mu}")
    click.echo(f"Log-price per block volatility (sigma): {sigma}")

    click.echo("Saving files ...")
    fp_root = fp[:-4]
    fp_params = fp_root + "_params.csv"
    df_params = pd.DataFrame(data={"mu": [mu], "sigma": [sigma]})
    df_params.to_csv(fp_params, index=False)
    click.echo(f"Fit params saved: {fp_params}")

    # save prob plot
    fp_prob = fp_root + "_probplot.png"
    _ = probplot(data, plot=plt)
    plt.savefig(fp_prob)
    click.echo(f"Probability plot saved: {fp_prob}")

    # save fit distribution on top of log-price histogram
    fp_hist = fp_root + "_hist.png"
    size = data.count()
    x = np.arange(-size // 2, size // 2 + 1, 1) / size
    x_lim_max = 1.1 * np.max([data.max(), np.abs(data.min())])
    ax = df.plot(
        y='dlog(p)', kind='hist', bins=200, color='w', edgecolor='black', density=True, xlim=(-x_lim_max, x_lim_max)
    )

    pdf = norm.pdf(x, loc=params[-2], scale=params[-1])
    df_pdf = pd.DataFrame(data={'norm': pdf}, index=x)
    df_pdf.plot(ax=ax)
    ax.get_figure().savefig(fp_hist)
    click.echo(f"Histogram plot saved: {fp_hist}")
