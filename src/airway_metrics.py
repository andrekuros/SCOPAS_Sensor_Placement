"""
Métricas por Aerovia (Flight Corridors)

Calcula métricas SCOPAS separadamente para cada aerovia (altitude de voo).
Exclui volumes ocupados por prédios do cálculo.
"""

import numpy as np
from typing import Dict, List, Tuple
from sensors import Sensor
from scopas_metrics import calculate_all_scopas_metrics


def calculate_metrics_per_airway(
    sensors: List[Sensor],
    p_net_grid: np.ndarray,
    redundancy_grid: np.ndarray,
    occupancy_grid: np.ndarray,
    airway_altitudes: List[float],
    voxel_resolution: float,
    z_min: float = 0.0,
    threshold: float = 0.8
) -> Dict[str, Dict]:
    """
    Calcula métricas SCOPAS para cada aerovia (altitude de voo).
    
    Volumes ocupados por prédios NÃO contam como área a ser coberta.
    
    Args:
        sensors: Lista de sensores
        p_net_grid: Grid 3D de P_Net
        redundancy_grid: Grid 3D de redundância
        occupancy_grid: Grid 3D de ocupação (0=livre, 1=prédio)
        airway_altitudes: Lista de altitudes das aerovias (ex: [20, 50, 100])
        voxel_resolution: Resolução do voxel em metros
        z_min: Altitude mínima do grid
        threshold: Threshold para considerar coberto
        
    Returns:
        Dict com métricas por aerovia:
        {
            '20m': {'Mc': ..., 'Mg': ..., ...},
            '50m': {'Mc': ..., 'Mg': ..., ...},
            '100m': {'Mc': ..., 'Mg': ..., ...}
        }
    """
    results = {}
    
    # Para cada aerovia
    for altitude in airway_altitudes:
        # Determinar layer(s) correspondente(s)
        layer_idx = int((altitude - z_min) / voxel_resolution)
        
        # Garantir que está dentro dos bounds
        if layer_idx < 0:
            layer_idx = 0
        if layer_idx >= p_net_grid.shape[2]:
            layer_idx = p_net_grid.shape[2] - 1
        
        # Extrair dados desta altitude
        p_net_layer = p_net_grid[:, :, layer_idx]
        redundancy_layer = redundancy_grid[:, :, layer_idx]
        occupancy_layer = occupancy_grid[:, :, layer_idx]
        
        # Máscara de células válidas (livres, não-ocupadas, não-NaN)
        valid_mask = (occupancy_layer == 0) & (~np.isnan(p_net_layer))
        
        # Células válidas
        valid_cells = p_net_layer[valid_mask]
        
        if valid_cells.size == 0:
            # Nenhuma célula válida nesta altitude
            results[f'{altitude}m'] = {
                'Mc': 0.0,
                'Mg': 1.0,
                'total_voxels': 0,
                'free_voxels': 0,
                'covered_voxels': 0,
                'avg_p_net': 0.0,
                'avg_redundancy': 0.0,
                'altitude': altitude,
                'layer_index': layer_idx
            }
            continue
        
        # Calcular métricas
        covered_cells = np.sum(valid_cells >= threshold)
        total_valid = valid_cells.size
        
        Mc = covered_cells / total_valid
        Mg = 1 - Mc
        
        # Redundância média (apenas de células válidas)
        redundancy_valid = redundancy_layer[valid_mask]
        avg_redundancy = np.mean(redundancy_valid)
        
        # P_Net média
        avg_p_net = np.mean(valid_cells)
        
        # Total de voxels
        total_voxels = p_net_layer.size
        occupied_voxels = np.sum(occupancy_layer == 1)
        free_voxels = total_voxels - occupied_voxels
        
        results[f'{altitude}m'] = {
            'Mc': float(Mc),
            'Mg': float(Mg),
            'total_voxels': int(total_voxels),
            'occupied_voxels': int(occupied_voxels),
            'free_voxels': int(free_voxels),
            'covered_voxels': int(covered_cells),
            'avg_p_net': float(avg_p_net),
            'avg_redundancy': float(avg_redundancy),
            'altitude': float(altitude),
            'layer_index': int(layer_idx),
            'coverage_percentage': float(Mc * 100)
        }
    
    return results


def calculate_aggregate_airway_metrics(
    airway_results: Dict[str, Dict],
    weights: Dict[str, float] = None
) -> Dict:
    """
    Calcula métricas agregadas ponderadas entre aerovias.
    
    Args:
        airway_results: Resultados por aerovia
        weights: Pesos por altitude (None = igual peso)
        
    Returns:
        Métricas agregadas
    """
    if weights is None:
        # Peso igual para todas as aerovias
        weights = {k: 1.0 for k in airway_results.keys()}
    
    # Normalizar pesos
    total_weight = sum(weights.values())
    weights = {k: v/total_weight for k, v in weights.items()}
    
    # Calcular médias ponderadas
    Mc_weighted = sum(airway_results[k]['Mc'] * weights.get(k, 0) 
                     for k in airway_results.keys())
    
    avg_redundancy_weighted = sum(airway_results[k]['avg_redundancy'] * weights.get(k, 0)
                                 for k in airway_results.keys())
    
    # Total de voxels livres
    total_free = sum(airway_results[k]['free_voxels'] for k in airway_results.keys())
    total_covered = sum(airway_results[k]['covered_voxels'] for k in airway_results.keys())
    
    return {
        'Mc_weighted': float(Mc_weighted),
        'Mg_weighted': float(1 - Mc_weighted),
        'avg_redundancy_weighted': float(avg_redundancy_weighted),
        'total_free_voxels': int(total_free),
        'total_covered_voxels': int(total_covered),
        'per_airway': airway_results
    }


def format_airway_results_table(airway_results: Dict[str, Dict]) -> str:
    """
    Formata resultados por aerovia em tabela ASCII.
    
    Args:
        airway_results: Resultados calculate_metrics_per_airway
        
    Returns:
        String formatada como tabela
    """
    lines = []
    lines.append("="*90)
    lines.append("MÉTRICAS POR AEROVIA (Flight Corridors)")
    lines.append("="*90)
    lines.append("")
    lines.append(f"{'Aerovia':<10} {'Mc (%)':<10} {'Mg (%)':<10} {'Redund.':<10} "
                f"{'Voxels Livres':<15} {'Cobertos':<10} {'P_Net Méd.':<12}")
    lines.append("-"*90)
    
    # Ordenar por altitude
    sorted_airways = sorted(airway_results.items(), 
                           key=lambda x: x[1]['altitude'])
    
    for airway_name, metrics in sorted_airways:
        lines.append(
            f"{airway_name:<10} "
            f"{metrics['Mc']*100:<10.2f} "
            f"{metrics['Mg']*100:<10.2f} "
            f"{metrics['avg_redundancy']:<10.2f} "
            f"{metrics['free_voxels']:<15} "
            f"{metrics['covered_voxels']:<10} "
            f"{metrics['avg_p_net']:<12.3f}"
        )
    
    lines.append("-"*90)
    lines.append("")
    lines.append("INTERPRETAÇÃO:")
    lines.append("  • Mc: Fração da aerovia coberta (maior = melhor)")
    lines.append("  • Mg: Fração de gaps (menor = melhor)")
    lines.append("  • Redund.: Média de sensores detectando (maior = mais robusto)")
    lines.append("  • Voxels Livres: Espaço disponível nesta altitude (exclui prédios)")
    lines.append("")
    lines.append("OBSERVAÇÕES:")
    lines.append("  • Altitudes maiores: Menos oclusão → Maior cobertura")
    lines.append("  • Altitudes menores: Mais prédios bloqueiam → Menor cobertura")
    lines.append("  • Redundância: Geralmente aumenta com altitude (mais LoS)")
    lines.append("="*90)
    
    return "\n".join(lines)

