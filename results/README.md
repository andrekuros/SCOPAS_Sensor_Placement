# Results directory

Optimization and analysis outputs are written here. The folder is **gitignored** by default (large, regenerable). Only this `README.md` is tracked.

## Layout

Standard pattern:

```text
results/<experiment_name>/<run_id>/
```

Key files (after optimization + tools):

| File | Description |
|------|-------------|
| `config.json` | Copy of the config used |
| `evaluation_results.json` | Pareto set with metrics |
| `pareto_front.json` | Pareto front subset |
| `evolution_logbook.json` | NSGA evolution stats (if saved) |
| `pareto_front.png`, `pareto_front_3d.png` | Cost vs coop/noncoop (or legacy) |
| `pareto_dual_layer_targets.png` | Coop × noncoop with requirement box |
| `requirement_solutions.json` | Feasible set from `select_requirement_solutions.py` |
| `overview_2d.png` | LoS-aware \(P_\mathrm{Net}\) overview |
| other `*.png` / `coverage_maps/` | Figures from `tools/` |

## Split objectives (`--split-objectives`)

For `configs/point_defense_airport_sjc.json`, `run_experiment.py` runs **coop_only** and **noncoop_only** sequentially. With the default `output.run_id` of `airport_run`, results appear as:

- `results/point_defense_airport_sjc/airport_run_coop/`
- `results/point_defense_airport_sjc/airport_run_noncoop/`

(suffix comes from `--run-id-suffix` combined with the base `run_id` in `run_framework.py`.)

## Acoustic and target demos

```bash
python run_experiment.py --config configs/demo_acoustic_dual_layer.json --skip-3d
python run_experiment.py --config configs/demo_acoustic_noncoop.json --skip-3d
python run_experiment.py --config configs/demo_acoustic_split.json --split-objectives --skip-3d
python run_experiment.py --config configs/demo_targets_coop90_noncoop35.json --skip-3d
python run_experiment.py --config configs/demo_targets_coop90_noncoop50.json --skip-3d
```

Typical output folders:

- `results/demo_acoustic_dual_layer/demo_dual/`
- `results/demo_targets_coop90_noncoop35/run_practical/`
- `results/demo_targets_coop90_noncoop50/run_targets/`

Filter by floors:

```bash
python tools/select_requirement_solutions.py \
  --results results/demo_targets_coop90_noncoop50/run_targets/ \
  --min-coop 0.90 --min-noncoop 0.35
```

See `docs/DEMO_RUNS.md` for interpretation and measured snapshots.

## Cleaning

```bash
# Remove generated runs (Unix)
rm -rf results/*/
```

Re-run experiments from the repo root using `run_framework.py` or `run_experiment.py`.
