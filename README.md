# kodiak-simulations-2023-07

Economic simulations for [Kodiak](https://kodiak.finance).

See the [supplementary note](https://hackmd.io/@fmrmf/Byk9XP-in) for derivations of the math expressions implemented in the repo.

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
Pool liquidity (L): 20327458074304365775
Pool sqrt price (sqrtPriceX96): 1737122892402026829622771365810543
Pool fee (f): 0.0005
Pool tick spacing in natural log terms (delta_min): 0.0004999750016664899
Rebalance period in blocks (tau): 7200
Avg fees from fee growth with token0 in (theta0): 1.1001210938989522e-08
Avg fees from fee growth with token1 in (theta1): 1.133334610430014e-08
Avg fees per unit of virtual liquidity over last rebalance period (theta): 1.1167278521644831e-08
Amount of token1 to LP: 1000000000000000000000
Liquidity to deploy per unit of virtual liquidity (l): 0.0022437060869181266
Log-price per block drift (mu): 2.6549742469970873e-07
Log-price per block volatility (sigma): 0.0004546440886143422
Minimum theta for +EV at infinite tick width (approx): 2.5895628019841654e-08
Rewards per unit of virtual liquidity (R): 2.5895628019841654e-08
Optimizing EV with respect to tick width ...
Result from scipy.optimize.minimize ...
  message: CONVERGENCE: REL_REDUCTION_OF_F_<=_FACTR*EPSMCH
  success: True
   status: 0
      fun: -2.0051472860350956
        x: [ 4.284e-02]
      nit: 2
      jac: [ 8.926e-05]
     nfev: 8
     njev: 4
 hess_inv: <1x1 LbfgsInvHessProduct with dtype=float64>
Optimal tick width (delta): 0.042836802956467614
Expected value at optimal tick width (E[V(tau)/V(0)]): 1.0025736430175478
Expected yield at optimal tick width (E[V(tau)/V(0)-1]): 0.002573643017547811
Current tick: 199918
Suggested lower tick for next period: 199495
Suggested upper tick for next period: 200345
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
Runner type (UniswapV3LPFullRunner, UniswapV3LPSimpleRunner): UniswapV3LPSimpleRunner
Runner kwarg (ref_addrs) [{}]: {"pool": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640", "manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"}
Runner kwarg (acc_addr) defaults to None. Do you want to input a value? [y/N]: N
Runner kwarg (tick_width) [0]: 2800
Runner kwarg (blocks_between_rebalance) [0]: 7200
Runner kwarg (compound_fees_at_rebalance) [False]: True
Input amount0, amount1, or liquidity? (liquidity, amount0, amount1): amount1
amount1 [0]: 1000000000000000000000
Start block number: 16219692
Stop block number [-1]: 16867692
Step size [1]: 2400
Setting up runner ...
```
