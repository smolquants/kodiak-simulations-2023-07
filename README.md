# kodiak-simulations-2023-07

Economic simulations for [Kodiak](https://kodiak.finance).

## Replication

To check the results, clone the repo

```sh
git clone https://github.com/smolquants/kodiak-simulations-2023-07.git
```

Install dependencies with [`hatch`](https://github.com/pypa/hatch) and [`ape`](https://github.com/ApeWorX/ape)

```sh
hatch build
hatch shell
(kodiak-simulations-2023-07) $ ape plugins install .
```

Setup your environment with an [Alchemy](https://www.alchemy.com) key

```sh
export WEB3_ALCHEMY_PROJECT_ID=<YOUR_PROJECT_ID>
```

Then launch [`ape-notebook`](https://github.com/ApeWorX/ape-notebook)

```sh
(kodiak-simulations-2023-07) $ ape notebook
```

## Scripts

Scripts using backtester contracts rely on [`backtest-ape`](https://github.com/smolquants/backtest-ape) and
[`ape-foundry`](https://github.com/ApeWorX/ape-foundry) mainnet-fork functionality. These produce backtest results
for different tick range strategies.

Compile the needed contracts

```sh
(kodiak-simulations-2023-07) ape compile --size
```

Then run the backtest script e.g. for fee 0 amounts

```sh
(kodiak-simulations-2023-07) ape run backtester
INFO: Starting 'anvil' process.
You are connected to provider network ethereum:mainnet-fork:foundry.
Runner type (UniswapV3LPFixedWidthFee0Runner, UniswapV3LPFixedWidthFee1Runner): UniswapV3LPFixedWidthFee0Runner
Runner kwarg (ref_addrs) [{}]: {"pool": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640", "manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"}
Runner kwarg (acc_addr) defaults to None. Do you want to input a value? [y/N]: N
Runner kwarg (tick_lower) [0]: 200280
Runner kwarg (tick_upper) [0]: 207240
Runner kwarg (amount_weth) [0]: 67000000000000000000
Runner kwarg (amount_token) [0]: 34427240000
Runner kwarg (tick_width) [0]: 6960
Runner kwarg (blocks_between_rebalance) [0]: 50400
Runner kwarg (block_rebalance_last) [0]: 16219692
Method (backtest, replay, forwardtest): backtest
Start block number: 16219692
Stop block number [-1]:
Step size [1]:
Setting up runner ...
```
