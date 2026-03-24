# Data directory

GeoJSON inputs for **SCOPAS** scenarios.

## Layout

| Path | Contents |
|------|----------|
| `examples/` | Synthetic benchmark scenes (e.g. 1 km × 1 km city grid) |
| `scenes/` | Packaged scenes (airport, stadium, farm, central district) |
| `case_studies/` | Optional real-area studies (e.g. Avenida Paulista — OSM download required) |

## GeoJSON expectations

- **Buildings**: polygons with a `height` attribute (metres).
- **Sensor candidates**: points with a `height` attribute (metres).

Paths in configs are relative to the **project root** unless absolute.

## Adding data

**From OpenStreetMap:**

```bash
python src/download_osm.py --city avenida_paulista --lat -23.5613 --lon -46.6563 --radius 2000 --output data/case_studies/avenida_paulista
```

**Bring your own GeoJSON** into `data/examples/`, `data/scenes/<name>/`, or `data/case_studies/<name>/`, then point `environment.buildings_file` and `environment.sensor_locations_file` at those files.

See also `docs/QUICK_INTEGRATION_TUTORIAL.md`.
