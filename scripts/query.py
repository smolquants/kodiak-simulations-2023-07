import click
import pandas as pd

from ape import Contract, chain, networks


def main():
    """
    Main query script for gathering historical price data from given pool.
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

    # ask user for uni v3 pool data
    # @dev must conform to univ3 core abi
    pool_addr = click.prompt("Pool address", type=str)
    pool = Contract(pool_addr)

    # ask user for output file path, start, stop, step
    fp = click.prompt("Path to write price history csv", type=str)
    start = click.prompt("Start block", type=int)
    stop = click.prompt("Stop block", type=int, default=-1)
    step = click.prompt("Step (blocks between queries)", type=int, default=1)

    if stop < 0:
        stop = last_block_number

    # Query pool price over historical blocks
    click.echo(f"Querying price from block {start} to block {stop} with step size {step} ...")
    is_head = True
    for block in range(start, stop, step):
        click.echo(f"Processing block {block} ...")

        # get the sqrt price data at block
        slot0 = pool.slot0(block_identifier=block)
        row = {'block_number': [block], 'sqrt_price_x96': [slot0.sqrtPriceX96]}
        click.echo(f"Pool slot0.sqrtPriceX96 at block {block}: {slot0.sqrtPriceX96}")

        # convert to pdf dataframe then append to file
        df = pd.DataFrame(data=row)
        df.to_csv(fp, mode='a', index=False, header=is_head)

        if is_head:
            is_head = False
