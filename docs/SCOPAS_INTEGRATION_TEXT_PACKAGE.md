# SCOPAS Integration Text Package (Point D Deliverable)

## Section A — Integration Rationale (for direct insertion)

### A.1 Positioning within the Point D architecture

This deliverable adopts a layered interpretation in which SCOPAS and DAIDALUS are complementary modules within the same safety argument. DAIDALUS remains the tactical Remain Well Clear (RWC) engine for conflict alerting and maneuver guidance, while SCOPAS operates upstream as the infrastructure design and planning layer that optimizes where sensing resources should be deployed before tactical logic is executed in operations.

In practical terms:

- DAIDALUS answers: "Given current states and uncertainties, which tactical action preserves Well Clear?"
- SCOPAS answers: "Given scenario geometry, costs, and mission constraints, which sensor network best supports cooperative and non-cooperative surveillance performance?"

This separation is consistent with Point D language in `Relat_D (4).pdf`, which emphasizes standards-aligned RWC/CA tactical behavior (DO-365B framing) while also requiring evidence that the "sense" layer is technically justified and scalable under real constraints (SWaP, density, uncertainty, and operational classes G/E/D/C).

### A.2 Traceability from infrastructure design to tactical performance

SCOPAS supports traceability from architecture assumptions to expected tactical quality by quantifying:

1. cooperative weighted protection (`M_wp_coop`);
2. non-cooperative weighted protection (`M_wp_noncoop`);
3. fused resilience (simultaneous cooperative + non-cooperative observability); and
4. investment burden (deployment cost, site count, and ROI-style indicators).

Therefore, SCOPAS does not replace tactical validation (HTLV/DAIDALUS), but constrains and justifies tactical scenario realism by providing defensible sensing baselines and trade-space evidence.

### A.3 Recommended text for integration sentence (short form)

> In this work, SCOPAS is integrated as the pre-tactical optimization layer of the Point D architecture, producing quantitatively justified sensor-network designs (cooperative and non-cooperative) that feed and contextualize DAIDALUS-based RWC tactical assessments.

---

## Section B — SCOPAS Solution Description

### B.1 Problem statement

SCOPAS solves a multi-objective sensor placement problem in 3D urban/airport scenes under occlusion and cost constraints. The objective is to derive Pareto-optimal deployments that balance threat-weighted protection and economic feasibility for BVLOS operations in non-segregated airspace.

### B.2 Inputs and scenario model

Core inputs:

- building geometry and height (GeoJSON polygons);
- candidate sensor sites and height (GeoJSON points);
- sensor models (Radar, RF, EO, Acoustic) with range/elevation/FOV/cost parameters;
- airway altitudes and critical assets (for weighted point-defense metrics);
- optimization settings (`n_samples`, `generations`, `n_cores`, min/max sensors).

Scenes used in this package:

- synthetic city benchmark (`configs/pareto_city_10x10_final.json`);
- real airport SJC point-defense case (`configs/point_defense_airport_sjc.json`).

### B.3 Optimization and objective profiles

SCOPAS supports three practical optimization profiles:

- `dual_layer`: optimize `(M_wp_coop, M_wp_noncoop, cost)`;
- `coop_only`: optimize `(M_wp_coop, cost)`;
- `noncoop_only`: optimize `(M_wp_noncoop, cost)`.

For operational planning, split execution (`--split-objectives`) is recommended because it yields separate Pareto fronts that avoid masking non-cooperative limitations under strong cooperative coverage.

### B.4 Analysis pipeline and outputs

`run_experiment.py` executes optimization plus post-processing:

- 2D/3D Pareto plots;
- coverage maps and 2D overview;
- hypervolume and convergence behavior;
- coverage by flight level;
- cost-vs-coverage threshold analysis;
- 3D export (`best_solution_3d.json`) and Cesium export (`cesium_data.json`) when scene metadata is available.

---

## Section C — Optimization Results Compendium (Measured + Discussion)

### C.1 City benchmark (`pareto_city_10x10_final`)

Configuration and runtime evidence (from `results/full_city_then_airport.log`):

- 196 buildings, 221 candidate sites, 12,005 voxels (9,921 free voxels);
- NSGA-II with population 100, generations 50, 6 cores;
- optimization completed in 28,914 s (~8.0 h);
- Pareto size: 100 solutions.

Best-individual snapshot in this run:

- `M_wp_coop = 0.928`;
- `M_wp_noncoop = 0.139`;
- `fused_resilience = 0.091`;
- cost = USD 470,000 (13 sites / 13 sensors);
- asset ROI = USD 506,476.

Interpretation:

- Cooperative protection is high, while non-cooperative protection remains limited in the same best snapshot, indicating a strong tension between RF-supported detectability and Radar/EO/Acoustic dark-target detectability in dense urban geometry.
- The wide Pareto set is useful for policy trade studies, but point recommendations should depend on explicit non-cooperative minimum requirements, not only aggregate cooperative scores.

Execution caveat:

- Full city post-processing stopped at Cesium export (`scene_meta.json not found`) because synthetic examples do not include scene georeference metadata required by `export_for_cesium.py`. Optimization and core plots/maps were still generated.

### C.2 Airport SJC split runs (`point_defense_airport_sjc`)

#### C.2.1 Cooperative profile (`airport_run_coop`)

Measured outputs:

- NSGA-II completed in 4,170.72 s (~69.5 min);
- Pareto size: 19;
- best snapshot: `M_wp_coop = 1.000`, `M_wp_noncoop = 0.048`, cost = USD 320,000;
- hypervolume = 125,211.699640 (normalized 10.2277).

Flight-level analysis (threshold 80%):

- top solutions report aggregate `Mc = 100%` at 20 m / 45 m / 65 m.

Cost-vs-coverage:

- `M_wp_coop` targets 70-95% are achieved at USD 90,000 (3 sensors);
- no solution reaches analogous high non-cooperative thresholds in this cooperative-optimized front.

Interpretation:

- Cooperative-only optimization yields excellent compliant-traffic coverage at low cost, but does not ensure non-cooperative detectability.

#### C.2.2 Non-cooperative profile (`airport_run_noncoop`)

Measured outputs:

- NSGA-II completed in 3,324.22 s (~55.4 min);
- Pareto size: 32;
- best snapshot: `M_wp_coop = 0.483`, `M_wp_noncoop = 0.483`, `fused_resilience = 0.255`;
- cost = USD 520,000 (8 sites / 8 sensors);
- hypervolume = 1,525,035.280438 (normalized 8.2645).

Flight-level analysis (illustrative top 3):

- Solution 1: USD 115,000, aggregate `Mc = 10.5%`;
- Solution 2: USD 455,000, aggregate `Mc = 48.2%`;
- Solution 3: USD 170,000, aggregate `Mc = 16.1%`.

Cost-vs-coverage:

- no feasible solution reaches `M_wp_noncoop` thresholds from 70% to 95% in this run.

Interpretation:

- Non-cooperative optimization is significantly harder and cost-intensive, revealing a current detectability ceiling for Radar/EO/Acoustic dark-target sensing under this scenario setup.
- This evidence is operationally valuable: it avoids overclaiming non-cooperative safety margins and indicates where additional sensing strategy, placement density, or model refinement is required.

### C.3 Cross-profile discussion (operational meaning)

- `coop_only` is suitable for compliant traffic management and capacity-oriented planning where cooperative observability is dominant.
- `noncoop_only` is the relevant profile for dark-target risk mitigation and should guide conservative safety claims.
- Reporting both profiles side by side provides a transparent safety narrative aligned with Point D emphasis on uncertainty handling and layered risk control.

---

## Section D — Potential, Limitations, and Risk-Aware Use

### D.1 Potential

1. Reproducible architecture planning with explicit trade-offs rather than single-point sensor choices.
2. Direct support for evidence-chain storytelling (design assumptions -> quantified observability -> tactical implications).
3. Fast portability to new geographies using GeoJSON scenes and templates.
4. Improved decision transparency for regulators and stakeholders through Pareto fronts and threshold-cost maps.

### D.2 Current limitations

1. **Scene metadata dependency for Cesium exports**: synthetic scenes without `scene_meta.json` cannot complete Cesium conversion.
2. **Assumption sensitivity**: results depend on voxel resolution, sensor parameterization, and objective-profile selection.
3. **Non-cooperative ceiling in tested airport setup**: high `M_wp_noncoop` thresholds (>=70%) were not reachable in the reported run.
4. **Computation cost**: high-fidelity urban runs can require multi-hour optimization windows.
5. **Not a tactical substitute**: SCOPAS evaluates sensing-network quality and must be paired with DAIDALUS/HTLV logic for full DAA claims.

### D.3 Recommended mitigation path

- keep split objective reporting as standard (`coop_only` + `noncoop_only`);
- add scenario-specific sensitivity sweeps (resolution, sensor mix, and placement constraints);
- use SCOPAS outputs as bounded assumptions for HTLV and DAIDALUS stress tests;
- report measured uncertainty margins explicitly to avoid overstated conclusions.

---

## Section E — Reproducibility Appendix Block (ready to paste)

### E.1 Environment validation

```bash
pip install -r requirements.txt
python run_framework.py --config configs/quick_test.json --mode nsga2
```

### E.2 City benchmark

```bash
python run_experiment.py --config configs/pareto_city_10x10_final.json --mode nsga2
# Optional for synthetic scenes without scene_meta:
python run_experiment.py --config configs/pareto_city_10x10_final.json --mode nsga2 --skip-3d
```

### E.3 Airport split benchmark

```bash
python run_experiment.py --config configs/point_defense_airport_sjc.json --split-objectives --mode nsga2
```

Expected outputs:

- `results/point_defense_airport_sjc/airport_run_coop/`
- `results/point_defense_airport_sjc/airport_run_noncoop/`

with:

- `evaluation_results.json`, `pareto_front.json`;
- `pareto_front.png`, `pareto_front_3d.png`;
- `coverage_maps/`, `overview_2d.png`;
- `evolution_convergence.png`, `coverage_by_flight_level.png`;
- `cost_vs_coverage_level.png`, `hypervolume.json`;
- `best_solution_3d.json`, `cesium_data.json` (when metadata exists).

### E.4 Suggested wording for methodological placement

> SCOPAS was used as a pre-tactical infrastructure optimization framework to design and evaluate cooperative/non-cooperative sensing trade spaces. DAIDALUS remained the tactical RWC mechanism for conflict alerting and guidance. This separation preserves standards alignment while improving traceability from sensor-network design assumptions to operational safety claims.

