# Acoustic Demonstration Runs

Short, reproducible NSGA-II demos that exercise **Radar + RF + EO + Acoustic** (or non-coop subsets) on the synthetic city scene.

Sensor CapEx / range defaults used here:

| Type | Cost (USD) | Urban range | Layer |
|------|------------|-------------|-------|
| Radar | 50,000 | ~2 km | Non-coop |
| RF | 15,000 | ~250 m | Coop only |
| EO | 25,000 | ~150 m | Non-coop |
| Acoustic | 8,000 | ~300 m | Non-coop |

## Commands

From the repository root:

```bash
# 1) Dual-layer Pareto (M_wp_coop, M_wp_noncoop, cost)
python run_experiment.py --config configs/demo_acoustic_dual_layer.json --skip-3d

# 2) Non-cooperative only (Radar + EO + Acoustic)
python run_experiment.py --config configs/demo_acoustic_noncoop.json --skip-3d

# 3) Split coop / noncoop fronts
python run_experiment.py --config configs/demo_acoustic_split.json --split-objectives --skip-3d
```

Outputs land under:

```text
results/demo_acoustic_dual_layer/demo_dual/
results/demo_acoustic_noncoop/demo_noncoop/
results/demo_acoustic_split/demo_split_coop/
results/demo_acoustic_split/demo_split_noncoop/
```

Each folder includes `evaluation_results.json`, `pareto_front.json`, hypervolume, convergence, coverage maps, and cost-vs-coverage plots when the analysis pipeline completes.

## How to read the demos

1. **Dual-layer** — inspect whether cheap Acoustic nodes appear on the non-coop axis of the front while RF still drives cooperative coverage.
2. **Non-coop only** — expect denser Acoustic (and some EO) selections when budget is tight; Radar appears when longer reach is needed.
3. **Split** — compare `_coop` vs `_noncoop` folders side by side; do not collapse dark-target risk into a single cooperative score.

## Measured snapshot

Filled after a local demo run (population / generations are intentionally small for fast demos; treat as illustrative, not paper-grade).

| Run | Pareto size | Best snapshot (illustrative) |
|-----|-------------|------------------------------|
| `demo_dual` | *(pending)* | *(pending)* |
| `demo_noncoop` | *(pending)* | *(pending)* |
| `demo_split_coop` | *(pending)* | *(pending)* |
| `demo_split_noncoop` | *(pending)* | *(pending)* |

Re-run the commands above to refresh numbers, then update this table from each run’s `evaluation_results.json` (sort by `M_wp_noncoop` or `cost` as needed).

## Scaling up

For publication-grade fronts, switch to:

- `configs/pareto_city_10x10_final.json`
- `configs/point_defense_airport_sjc.json` with `--split-objectives`

and increase `pareto_search.n_samples` / `generations`. Keep Acoustic parameters documented in `docs/SENSORS.md` when reporting CapEx.
