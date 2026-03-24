# Real-world scenes (OSM)

Scenes are generated with `src/download_osm.py` from OpenStreetMap.

| Scene | Location | Description |
|-------|----------|-------------|
| **airport_sjc** | São José dos Campos Airport (-23.228, -45.863), 700 m radius | Airport/terminal area, 49 buildings, 50 sensor candidates |
| **stadium_arena** | Neo Química Arena region, São Paulo (-23.545, -46.474), 500 m radius | Stadium and surrounding area, 579 buildings, 57 sensor candidates |

## Regenerating data

```bash
# Airport (SJC)
python src/download_osm.py --city airport_sjc --lat -23.228 --lon -45.863 --radius 700 --output data/scenes/airport_sjc

# Stadium (Neo Química Arena area)
python src/download_osm.py --city stadium_arena --lat -23.54525 --lon -46.47428 --radius 500 --output data/scenes/stadium_arena
```

## DEM (terrain) for realistic optimization

To enable terrain-aware LoS (line-of-sight) and sensor placement:

```bash
pip install elevation rasterio
# System: GDAL, curl, unzip
python tools/download_dem.py --scene data/scenes/airport_sjc
```

Creates `scene_dem.tif` (SRTM). The optimization will use it automatically when present.

## Running Point Defense experiments

```bash
python run_framework.py --config configs/point_defense_airport_sjc.json --mode nsga2
python run_framework.py --config configs/point_defense_stadium_arena.json --mode nsga2
```
