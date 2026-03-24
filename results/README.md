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
| `pareto_front.png`, `overview_2d.png`, … | Figures from `tools/` |

## Split objectives (`--split-objectives`)

For `configs/point_defense_airport_sjc.json`, `run_experiment.py` runs **coop_only** and **noncoop_only** sequentially. With the default `output.run_id` of `airport_run`, results appear as:

- `results/point_defense_airport_sjc/airport_run_coop/`
- `results/point_defense_airport_sjc/airport_run_noncoop/`

(suffix comes from `--run-id-suffix` combined with the base `run_id` in `run_framework.py`.)

## Cleaning

```bash
# Remove generated runs (Unix)
rm -rf results/*/
# PowerShell: Remove-Item results\*\* -Recurse -Force (careful)
```

Re-run experiments from the repo root using `run_framework.py` or `run_experiment.py`.
