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
(kodiak-simulations-2023-07) ape plugins install .
```

Setup your environment with an [Alchemy](https://www.alchemy.com) key

```sh
export WEB3_ALCHEMY_PROJECT_ID=<YOUR_PROJECT_ID>
```

Then launch [`ape-notebook`](https://github.com/ApeWorX/ape-notebook)

```sh
(kodiak-simulations-2023-07) ape notebook
```

## Scripts

### Optimizer

Scripts related to determining the optimal tick width for the LP to use are (in intended order):

- `scripts/query.py`
- `scripts/fit.py`
- `scripts/optimize.py`

These rely on [`ape-foundry`](https://github.com/ApeWorX/ape-foundry) mainnet-fork functionality.

Run the query script to gather and store historical price data from a specified spot pool

```sh
(kodiak-simulations-2023-07) ape run query
INFO: Starting 'anvil' process.
You are connected to provider network ethereum:mainnet-fork:foundry.
Pool address: 0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640
Path to write price history csv: notebook/data/price_0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640_13143698_18399698_7200.csv
Start block: 13143698
Stop block [-1]: 18399698
Step (blocks between queries) [1]: 7200
Querying price from block 13143698 to block 18399698 with step size 7200 ...
Processing block 13143698 ...
Pool slot0.sqrtPriceX96 at block 13143698: 1292692512533636681812260363304234
```

Fit the gathered data to a [GBM](https://en.wikipedia.org/wiki/Geometric_Brownian_motion) price process

```sh
(kodiak-simulations-2023-07) ape run fit
INFO: Starting 'anvil' process.
Path to price history csv: notebook/data/price_0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640_13143698_18399698_7200.csv
Fitting log-price history to GBM ...
Returned fit params for candles in csv: (0.0011674569675148257, 0.03857783017026948)
Log-price per block drift (mu): 2.6549742469970873e-07
Log-price per block volatility (sigma): 0.0004546440886143422
Saving files ...
Fit params saved: notebook/data/price_0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640_13143698_18399698_7200_params.csv
Probability plot saved: notebook/data/price_0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640_13143698_18399698_7200_probplot.png
Histogram plot saved: notebook/data/price_0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640_13143698_18399698_7200_hist.png
```

The returned drift `[mu]` and volatility `[sigma]` parameters will be used as inputs to the tick width optimization script.

You shouldn't have to run query and fit scripts that frequently if enough historical price data was fetched for the pool,
given the assumed nature of the price process.

Then run the optimization script

```sh
(kodiak-simulations-2023-07) ape run optimize
INFO: Starting 'anvil' process.
You are connected to provider network ethereum:mainnet-fork:foundry.
Start block for LP [-1]:
Pool address: 0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640
Pool liquidity (L): 21222482588437805967
Pool sqrt price (sqrtPriceX96): 1943643613257695920613088162082351
Pool fee (f): 0.0005
Pool tick spacing in natural log terms (delta_min): 0.0004999750016664899
Rebalance period in blocks (tau): 50400
Avg fees from fee growth with token0 in (theta0): 6.504326568279474e-09
Avg fees from fee growth with token1 in (theta1): 6.462400985125087e-09
Avg fees per unit of virtual liquidity over last rebalance period (theta): 6.4833637767022804e-09
Amount of token1 to LP: 1000000000000000000000
Liquidity to deploy per unit of virtual liquidity (l): 0.0019207319570034528
Log-price per block drift (mu): 2.6549742469970873e-07
Log-price per block volatility (sigma): 0.0004546440886143422
Minimum theta for +EV at infinite tick width (approx): 2.5887283125403797e-08
WARNING: Not enough fees over last rebalance period for +EV LPing at infinite tick width when ignoring drift (approx).
Proceed anyway? [y/N]: y
Optimizing EV with respect to tick width ...
Result from scipy.optimize.minimize:   message: CONVERGENCE: NORM_OF_PROJECTED_GRADIENT_<=_PGTOL
  success: True
   status: 0
      fun: -2.011451230767496
        x: [ 1.042e+01]
      nit: 16
      jac: [-5.551e-06]
     nfev: 34
     njev: 17
 hess_inv: <1x1 LbfgsInvHessProduct with dtype=float64>
Optimal tick width (delta): [10.422413]
Expected value at optimal tick width (E[V(tau)/V(0)]): [1.00572562]
Expected yield at optimal tick width (E[V(tau)/V(0)-1]): [0.00572562]
Current tick: 202164
Suggested lower tick for next period: 97931
Suggested upper tick for next period: 306389
```

which will output the optimal tick width, expected yield, and recommended lower and upper ticks to console.


### Backtester

Scripts using backtester contracts rely on [`backtest-ape`](https://github.com/smolquants/backtest-ape) and
[`ape-foundry`](https://github.com/ApeWorX/ape-foundry) mainnet-fork functionality. These produce backtest results
for different tick range strategies.

Compile the needed contracts

```sh
(kodiak-simulations-2023-07) ape compile --size
```

Then run the backtest script

```sh
(kodiak-simulations-2023-07) ape run backtester
INFO: Starting 'anvil' process.
You are connected to provider network ethereum:mainnet-fork:foundry.
Runner type (UniswapV3LPFixedWidthRunner): UniswapV3LPFixedWidthRunner
Runner kwarg (ref_addrs) [{}]: {"pool": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640", "manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"}
Runner kwarg (acc_addr) defaults to None. Do you want to input a value? [y/N]: N
Runner kwarg (tick_width) [0]: 240
Runner kwarg (blocks_between_rebalance) [0]: 50400
Input amount0, amount1, or liquidity? (liquidity, amount0, amount1): amount0
amount0 [0]: 557807489
Start block number: 16219692
Stop block number [-1]: 16867692
Step size [1]: 2400
Setting up runner ...
```
