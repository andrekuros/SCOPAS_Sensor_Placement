# 3D visualization

**Three.js** viewer for the exported best solution (`best_solution_3d.json`). Cesium exports (`cesium_data.json`) are plain JSON for use with any Cesium-based app; this repo does not ship a bundled Cesium HTML page.

## 1. Export JSON (from a results run)

From the project root, pass a **results directory** or a results JSON file:

```bash
python tools/export_best_solution_3d.py --results results/<experiment_name>/<run_id>/
```

This writes `best_solution_3d.json` in that folder (includes point-defense metrics when `critical_assets` is set).

## 2. Serve and open the Three.js viewer

Because the page loads JSON with `fetch`, use a local HTTP server from the **repo root**:

```bash
python -m http.server 8000
```

Then open:

`http://localhost:8000/visualizations/view_best_solution_3d.html?data=results/<experiment_name>/<run_id>/best_solution_3d.json`

## 3. Cesium (`cesium_data.json`)

```bash
python tools/export_for_cesium.py --results results/<experiment_name>/<run_id>/
```

Requires `scene_meta.json` in the scene directory (see `data/scenes/airport_sjc/`). Synthetic `data/examples/` scenes do not include it — use `--skip-3d` on `run_experiment.py` or add metadata for your scene.

## Controls (Three.js)

- **Left-drag**: rotate  
- **Scroll**: zoom  
- **Right-drag**: pan  

Sensor colors: Radar (red), RF (blue), EO (green).
