# SCOPAS Paper Rerun — Manifest

**Source framework:** [andrekuros/SCOPAS_Sensor_Placement](https://github.com/andrekuros/SCOPAS_Sensor_Placement)  
**Paper target repo:** [andrekuros/Sensor-Placement-UTM](https://github.com/andrekuros/Sensor-Placement-UTM)  
**SCOPAS branch:** `cursor/acoustic-sensor-2dc7`  
**Date:** 2026-07-30

## Push status

Cloud-agent GitHub token is scoped to `SCOPAS_Sensor_Placement` and **cannot push** to `Sensor-Placement-UTM`.

**On your machine** (with write access), sync the paper package in one command:

```bash
./tools/sync_paper_to_utm.sh
```

Flags: `--dry-run`, `--no-push`, `--dest ~/code/Sensor-Placement-UTM`, `--branch main`.

Manual alternative:

## Experiments completed

| ID | Config | Budget | Outcome |
|----|--------|--------|---------|
| City dual | `paper_rerun_city_dual.json` | 32×18, res 30 m, 5 assets | **Done** — 32 sols; coop 0.07–0.96; noncoop 0.00–0.56 |
| Airport coop | `paper_rerun_airport_sjc.json` coop_only | 24×12, res 40 m | **Done** — coop≥0.90 from **$61k**; noncoop≈0 |
| Airport noncoop | same, noncoop_only | 24×12, res 40 m | **Done** — noncoop max **0.445** @ $405k |
| Paulista lite | `paper_rerun_paulista_lite.json` | 24×10, res 40 m | **Done** — 24 sols; coop to 0.97; noncoop max **0.254** |
| Targets 90/35 & 90/50 | `demo_targets_*` | short prior demos | **Done** — joint 90/35 feasible on stretch front @ $315k |
| Control A (oracle) | `tools/paper_controls_ab.py` | n∈{8,10,12}, k∈{3,4,5}, res 40 m | **Done** — GA ΔMc ≤0.3 pp vs oracle |
| Control B (ablation) | same | budgets $31k/$76k/$150k | **Done** — RF wins lean/mid; hetero edges @ $150k |
| Control C (dual CapEx) | `--only-c` + `paper_rerun_city_dual.json` | $31k/$76k/$150k/$320k | **Done** — RF wins coop (nc=0); hetero wins noncoop @ $320k (47.5%, coop≈83%) |

Artifacts: `paper_utm/results/controls/`, `paper_utm/tables/tab_oracle_comparison.tex`, `paper_utm/tables/tab_modality_ablation*.tex`.

## Headline findings (vs old single-metric paper)

1. **Coop is cheap; noncoop is not.** SJC: \(M_{wp,coop}\geq0.90\) at $61k vs best noncoop 0.445 at $405k.
2. **Joint floors:** practical corridor near **90% coop / 35% noncoop** on synthetic geometry; **50% noncoop** with ≥90% coop remains stretch.
3. **Dense real cities hurt dark-target coverage more:** Paulista lite noncoop max only ~0.25 in this budget.
4. **Split fronts are mandatory** for honest BVLOS claims — coop optima leave noncoop near zero.
5. **Control A:** small-$n$ GA matches oracle \(M_c\) within 0.0–0.3 pp (same ray-tracer); city-scale optimality not claimed.
6. **Control B:** RF-only wins CapEx-matched classic \(M_c\) at $31k/$76k; heterogeneous only edges at $150k.
7. **Control C:** RF saturates \(M_{wp,coop}\) with 0 noncoop; EO/Radar win lean noncoop; **heterogeneous wins noncoop at $320k** (47.5% with companion coop ≈83%).

## Reproduce

```bash
python run_experiment.py --config configs/paper_rerun_city_dual.json --skip-3d
# Airport split (avoid checkpoint resume across profiles):
# set optimization.objectives to coop_only / noncoop_only separately, or use --split-objectives with checkpoint disabled
python run_experiment.py --config configs/paper_rerun_airport_sjc.json --split-objectives --skip-3d
python run_experiment.py --config configs/paper_rerun_paulista_lite.json --skip-3d
python3 tools/paper_controls_ab.py --resolution 40 --out results/paper_controls
python3 tools/paper_controls_ab.py --only-c --resolution 40 --out results/paper_controls \
  --dual-config configs/paper_rerun_city_dual.json
```

## City dual snapshot

- Closest to 90%/35%: coop=0.895, noncoop=0.434, $503k  
- Feasible 85%/35%: cheapest $320k (4 Radar + 2 RF)  
- Feasible 90%/30%: cheapest $433k  
- Coop≥90% path: $247k with noncoop only 0.134  

## Known issue

`--split-objectives` with checkpoint resume can crash when coop (4 types incl. RF) checkpoint is loaded into noncoop (3 types). Disable checkpoint or clear between profiles.
