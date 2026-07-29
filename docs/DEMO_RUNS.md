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

1. **Dual-layer** — cheap Acoustic nodes appear across the front; RF still drives high cooperative coverage; non-coop remains harder.
2. **Non-coop only** — Acoustic-heavy low-cost solutions appear first; Radar enters when higher \(M_{wp,noncoop}\) is required.
3. **Split** — compare `_coop` vs `_noncoop` folders side by side; do not collapse dark-target risk into a single cooperative score.

## Measured snapshot (this environment)

Illustrative demo settings (pop 12–16, gen 6–8). Not paper-grade; regenerate locally to refresh.

| Run | Pareto | Acoustic on front | Best coop snapshot | Best noncoop snapshot |
|-----|--------|-------------------|--------------------|------------------------|
| `demo_dual` | 16 | 15/16 sols (24 nodes) | \(M_{wp,coop}=0.949\), cost $206k (4 RF + 2 Acoustic + 1 EO) | \(M_{wp,noncoop}=0.410\), cost $311k (2 Radar + 3 EO + 2 Acoustic + 1 RF) |
| `demo_noncoop` | 16 | 15/16 sols (35 nodes) | — | \(M_{wp,noncoop}=0.410\), cost $413k (5 Radar + 2 EO + 1 Acoustic); cheapest: 3 Acoustic @ $69k |
| `demo_split_coop` | 12 | 11/12 sols (15 nodes) | \(M_{wp,coop}=0.960\), cost $253k | coop front does not push noncoop hard (\(M_{wp,noncoop}\approx0.18\)) |
| `demo_split_noncoop` | 12 | 11/12 sols (23 nodes) | — | \(M_{wp,noncoop}=0.482\), cost $394k (5 Radar + 3 Acoustic); cheapest: 2 Acoustic + 1 EO @ $86k |

**Takeaways from these demos**

- Acoustic is selected on nearly every Pareto member (low CapEx filler for non-coop / local coverage).
- Cooperative coverage ≥90% remains inexpensive with RF (+ Acoustic); non-cooperative coverage ≥70% was **not** reached in these short runs (same structural finding as earlier airport/city studies).
- Split optimization is required to expose dark-target cost: noncoop best \(M_{wp,noncoop}\) (~0.41–0.48) far exceeds the dual-layer “best coop” individual’s noncoop score (~0.04).

Hypervolumes (raw): dual `32369`, noncoop `682830`, split_coop `49340`, split_noncoop `493894`.

## Target-seeking dual-layer experiments

Aim for explicit dual-layer floors instead of open Pareto exploration alone:

| Config | Targets | Rationale |
|--------|---------|-----------|
| `configs/demo_targets_coop90_noncoop35.json` | coop ≥90%, noncoop ≥35% | Practical floor (prior demos often reach ~35–48% noncoop) |
| `configs/demo_targets_coop90_noncoop50.json` | coop ≥90%, noncoop ≥50% | Stretch dark-target requirement |

```bash
python run_experiment.py --config configs/demo_targets_coop90_noncoop35.json --skip-3d
python run_experiment.py --config configs/demo_targets_coop90_noncoop50.json --skip-3d

# Filter Pareto for cheapest feasible under the config targets
python tools/select_requirement_solutions.py \
  --results results/demo_targets_coop90_noncoop35/run_practical/
python tools/select_requirement_solutions.py \
  --results results/demo_targets_coop90_noncoop50/run_targets/
```

Outputs: `requirement_solutions.json` (feasible set + cheapest) and `pareto_dual_layer_targets.png` (coop×noncoop with target box).

### Measured snapshot (this environment)

| Run | Targets | Feasible? | Cheapest feasible / closest miss |
|-----|---------|-----------|----------------------------------|
| `run_practical` | 90% / 35% | *(pending)* | *(pending)* |
| `run_targets` | 90% / 50% | *(pending)* | *(pending)* |

## Scaling up

For publication-grade fronts, switch to:

- `configs/pareto_city_10x10_final.json`
- `configs/point_defense_airport_sjc.json` with `--split-objectives`

and increase `pareto_search.n_samples` / `generations`. Keep Acoustic parameters documented in `docs/SENSORS.md` when reporting CapEx.
