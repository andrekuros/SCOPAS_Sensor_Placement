"""
Download de Dados Urbanos Reais do OpenStreetMap

Este módulo permite baixar prédios e criar locais de sensores para qualquer
cidade do mundo usando OpenStreetMap. Para cenas de aeroporto, também baixa
pistas (aeroway=runway) e salva meta para o visualizador (geo_bounds).
"""

import osmnx as ox
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point, LineString
import json
import argparse
from pathlib import Path


def _geo_bounds_from_utm_bounds(
    x_min: float, y_min: float, x_max: float, y_max: float, epsg_code: int
) -> dict:
    """
    Convert UTM bounds to WGS84 (south, north, west, east).
    Ensures map tiles align with scene coordinates.
    """
    from shapely.geometry import box
    b = box(x_min, y_min, x_max, y_max)
    gdf = gpd.GeoDataFrame(geometry=[b], crs=epsg_code)
    gdf_wgs = gdf.to_crs(epsg=4326)
    minx, miny, maxx, maxy = gdf_wgs.total_bounds
    return {"south": miny, "north": maxy, "west": minx, "east": maxx}


def download_city_data(
    city_name: str,
    latitude: float,
    longitude: float,
    radius_m: float = 800,
    output_dir: str = "data"
) -> tuple:
    """
    Baixa dados de prédios de uma cidade do OpenStreetMap.
    
    Args:
        city_name: Nome da cidade/região
        latitude: Latitude do centro
        longitude: Longitude do centro
        radius_m: Raio em metros
        output_dir: Diretório de saída
        
    Returns:
        (buildings_file, sensors_file): Caminhos dos arquivos gerados
    """
    print(f"Baixando dados de: {city_name}")
    print(f"Coordenadas: {latitude:.4f}, {longitude:.4f}")
    print(f"Raio: {radius_m}m\n")
    
    # Criar diretório de saída
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)
    
    # Baixar prédios
    print("1. Baixando prédios do OpenStreetMap...")
    try:
        buildings = ox.features_from_point(
            (latitude, longitude),
            tags={'building': True},
            dist=radius_m
        )
        print(f"   OK {len(buildings)} buildings downloaded")
    except Exception as e:
        print(f"   Erro: {e}")
        return None, None
    
    # Processar dados
    print("\n2. Processando dados...")
    buildings = buildings[buildings.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    buildings = buildings.reset_index(drop=True)
    
    # Estimar alturas
    if 'height' not in buildings.columns and 'building:levels' in buildings.columns:
        buildings['height'] = buildings['building:levels'].fillna(5) * 3.0
    elif 'height' not in buildings.columns:
        def estimate_height(row):
            return np.random.uniform(10, 30)
        buildings['height'] = buildings.apply(estimate_height, axis=1)
    else:
        buildings['height'] = pd.to_numeric(buildings['height'], errors='coerce').fillna(20.0)
    
    buildings['height'] = buildings['height'].clip(lower=5.0, upper=200.0)
    
    # Reprojetar para UTM
    print("\n3. Convertendo para coordenadas métricas...")
    # Determinar zona UTM baseada na longitude
    utm_zone = int((longitude + 180) / 6) + 1
    hemisphere = 'north' if latitude >= 0 else 'south'
    
    # EPSG code para UTM
    if hemisphere == 'north':
        epsg_code = 32600 + utm_zone
    else:
        epsg_code = 32700 + utm_zone
    
    buildings_utm = buildings.to_crs(epsg=epsg_code)
    
    # Transladar para origem (mesmo offset para runways depois)
    bounds = buildings_utm.total_bounds
    x_min, y_min, x_max, y_max = bounds
    buildings_utm['geometry'] = buildings_utm.geometry.translate(xoff=-x_min, yoff=-y_min)
    
    bounds_final = buildings_utm.total_bounds
    scene_meta = {
        "geo_bounds": _geo_bounds_from_utm_bounds(x_min, y_min, x_max, y_max, epsg_code),
        "utm_origin": [float(x_min), float(y_min)],
        "epsg": epsg_code,
    }
    area_km2 = ((bounds_final[2] - bounds_final[0]) * (bounds_final[3] - bounds_final[1])) / 1e6
    
    print(f"   Área: {bounds_final[2]:.0f}m × {bounds_final[3]:.0f}m ({area_km2:.2f} km²)")
    
    # Salvar prédios
    buildings_export = buildings_utm[['geometry', 'height']].copy()
    buildings_file = output_path / f"{city_name.lower().replace(' ', '_')}_buildings.geojson"
    buildings_export.to_file(buildings_file, driver='GeoJSON')
    print(f"\n4. Prédios salvos: {buildings_file}")
    
    # Gerar locais de sensores
    print("\n5. Gerando locais de sensores...")
    sensor_locations = generate_sensor_locations(
        buildings_utm,
        bounds_final,
        spacing=150  # 150m entre sensores
    )
    
    sensors_file = output_path / f"{city_name.lower().replace(' ', '_')}_sensors.geojson"
    with open(sensors_file, 'w') as f:
        json.dump(sensor_locations, f, indent=2)
    
    print(f"   OK {len(sensor_locations['features'])} sensor locations generated")
    print(f"   OK Saved: {sensors_file}")
    
    # Runways (aeroportos): buscar pistas OSM e salvar em coordenadas de cena
    runways_file = None
    try:
        print("\n6. Buscando pistas (aeroway=runway)...")
        runways = ox.features_from_point(
            (latitude, longitude),
            tags={"aeroway": "runway"},
            dist=radius_m,
        )
        if runways is not None and len(runways) > 0:
            runways = runways[runways.geometry.type.isin(["LineString", "MultiLineString", "Polygon"])]
            runways = runways.reset_index(drop=True)
            if len(runways) > 0:
                runways_utm = runways.to_crs(epsg=epsg_code)
                runways_utm["geometry"] = runways_utm.geometry.translate(xoff=-x_min, yoff=-y_min)
                # Exportar como LineStrings (extrair exterior para Polygon)
                features = []
                for idx, row in runways_utm.iterrows():
                    geom = row.geometry
                    props = {}
                    r = row.get("ref", None) if hasattr(row, "get") else getattr(row, "ref", None)
                    if r is not None:
                        props["ref"] = r[0] if isinstance(r, (list, tuple)) and r else str(r)
                    w = row.get("width", None) if hasattr(row, "get") else getattr(row, "width", None)
                    if w is not None:
                        props["width"] = str(w)
                    if geom.geom_type == "LineString":
                        coords = [[float(c[0]), float(c[1])] for c in geom.coords]
                        features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}, "properties": props})
                    elif geom.geom_type == "MultiLineString":
                        for line in geom.geoms:
                            coords = [[float(c[0]), float(c[1])] for c in line.coords]
                            features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}, "properties": props})
                    elif geom.geom_type == "Polygon":
                        coords = [[float(c[0]), float(c[1])] for c in geom.exterior.coords]
                        features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}, "properties": props})
                if features:
                    runways_geojson = {"type": "FeatureCollection", "features": features}
                    runways_file = output_path / f"{city_name.lower().replace(' ', '_')}_runways.geojson"
                    with open(runways_file, "w", encoding="utf-8") as f:
                        json.dump(runways_geojson, f, indent=2)
                    scene_meta["runways_file"] = runways_file.name
                    print(f"   OK {len(features)} runway(s) saved: {runways_file}")
                else:
                    print("   No runway geometries extracted")
            else:
                print("   No runways in area")
        else:
            print("   No runways in area")
    except Exception as e:
        print(f"   Runways skip: {e}")
    
    # Salvar meta para o visualizador (geo_bounds)
    scene_meta_path = output_path / "scene_meta.json"
    with open(scene_meta_path, "w", encoding="utf-8") as f:
        json.dump(scene_meta, f, indent=2)
    print(f"\n   Scene meta: {scene_meta_path}")
    
    # Estatísticas
    print(f"\n" + "="*70)
    print(f"OK Download complete!")
    print(f"="*70)
    print(f"Cidade: {city_name}")
    print(f"Prédios: {len(buildings_export)}")
    print(f"Altura média: {buildings_export['height'].mean():.1f}m")
    print(f"Área: {area_km2:.2f} km²")
    print(f"Sensores: {len(sensor_locations['features'])}")
    if runways_file:
        print(f"Pistas: {runways_file}")
    print(f"="*70)
    
    return str(buildings_file), str(sensors_file)


def generate_sensor_locations(buildings_gdf, bounds, spacing=150):
    """
    Gera locais de sensores em grid, evitando prédios.
    
    Args:
        buildings_gdf: GeoDataFrame de prédios
        bounds: (x_min, y_min, x_max, y_max)
        spacing: Espaçamento entre sensores (metros)
        
    Returns:
        GeoJSON de locais de sensores
    """
    x_min, y_min, x_max, y_max = bounds
    
    x_grid = np.arange(spacing/2, x_max, spacing)
    y_grid = np.arange(spacing/2, y_max, spacing)
    
    sensor_features = []
    sensor_id = 1
    
    for x in x_grid:
        for y in y_grid:
            point = Point(x, y)
            
            # Verificar se está dentro de prédio
            inside_building = False
            for _, building in buildings_gdf.iterrows():
                if building.geometry.contains(point):
                    inside_building = True
                    break
            
            if not inside_building:
                height = np.random.uniform(25, 35)  # 25-35m de altura
                
                sensor_features.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [float(x), float(y)]
                    },
                    'properties': {
                        'id': sensor_id,
                        'height': float(height),
                        'name': f'Sensor_{sensor_id}'
                    }
                })
                sensor_id += 1
    
    return {
        'type': 'FeatureCollection',
        'features': sensor_features
    }


def main():
    """Função principal com CLI."""
    parser = argparse.ArgumentParser(
        description='Download de dados urbanos do OpenStreetMap para análise SCOPAS'
    )
    parser.add_argument('--city', type=str, required=True,
                       help='Nome da cidade/região')
    parser.add_argument('--lat', type=float, required=True,
                       help='Latitude do centro')
    parser.add_argument('--lon', type=float, required=True,
                       help='Longitude do centro')
    parser.add_argument('--radius', type=float, default=800,
                       help='Raio em metros (padrão: 800)')
    parser.add_argument('--output', type=str, default='data',
                       help='Diretório de saída (padrão: data)')
    
    args = parser.parse_args()
    
    download_city_data(
        city_name=args.city,
        latitude=args.lat,
        longitude=args.lon,
        radius_m=args.radius,
        output_dir=args.output
    )


if __name__ == "__main__":
    main()


