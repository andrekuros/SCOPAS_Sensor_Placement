# Dual-Layer BVLOS Sensor Placement with SCOPAS (Paper Revision)

**Working title:** *Dual-Layer Multi-Objective Sensor Placement for Urban BVLOS Surveillance: Cooperative vs Non-Cooperative Coverage under CapEx Constraints*

This directory is a **SCOPAS-based revision package** for the paper previously developed in [Sensor-Placement-UTM](https://github.com/andrekuros/Sensor-Placement-UTM).

## What changed vs the old draft

| Old (MUSCAT / UTM draft) | New (SCOPAS) |
|--------------------------|--------------|
| Single fused \(M_c\) + redundancy + cost | Dual-layer \(M_{wp,coop}\), \(M_{wp,noncoop}\), cost |
| RF / Acoustic / EO narrative without dark-target split | Explicit non-coop set: Radar + EO + Acoustic |
| Synthetic city + Paulista only | City + **airport SJC split fronts** + requirement floors |
| “≈98% of optimum” baseline claim | Dropped; Control A small-$n$ oracle (\(\Delta M_c\leq0.3\) pp) |
| GREEN = \(M_c\geq0.75\), overlap ≥0.35 | Planning floors e.g. coop≥90%, noncoop≥35% |
| Dual-layer + Controls A–C | Related-work comparison table vs MUSCAT/SAND/Aievola + surveys |

## Package layout

```
paper_utm/
├── MANIFEST.md              # Run commands, numbers, sync note
├── README.md                # This file
├── main.tex                 # IEEE/AIAA DASC skeleton (update abstract from MANIFEST)
├── sections/                # LaTeX sections (results rewritten for dual-layer)
├── figures/scopas/          # Regenerated PNGs from SCOPAS runs
├── results/                 # evaluation_results.json + hypervolume + requirement filters
├── results/controls/        # Control A/B JSON (oracle + modality ablation)
├── tables/                  # Filled Control A/B LaTeX tables
└── references/
```

## Sync to Sensor-Placement-UTM (Overleaf)

From the SCOPAS repo root, with your GitHub credentials:

```bash
./tools/sync_paper_to_utm.sh
```

That clones/updates `andrekuros/Sensor-Placement-UTM`, copies `paper_utm/` to the paper repo root, commits, and pushes `main` (override with `--branch`).

Useful flags: `--dry-run`, `--no-push`, `--dest ~/path/to/Sensor-Placement-UTM`.

Then in Overleaf: **Import from GitHub** (or pull) that repo.

See `MANIFEST.md` for experiment status and measured city numbers.
